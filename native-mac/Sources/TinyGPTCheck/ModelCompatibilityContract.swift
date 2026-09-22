import Foundation

/// Schema-v2 operation/stage derivation plus the local `model-run` receipt
/// boundary. Static checks remain predictions; only a matching receipt can
/// upgrade an operation to `verified_on_this_device`.
public enum ModelCompatibilityContract {
    public static func enrich(
        _ source: ModelCheckReport,
        hasHFAccess: Bool,
        receipt: ModelCheckReport.VerificationReceipt? = nil
    ) -> ModelCheckReport {
        var report = source
        report.schemaVersion = 2
        report.operations = deriveOperations(report, hasHFAccess: hasHFAccess)
        report.executionStages = deriveStages(report)
        report.verificationReceipt = nil

        guard let receipt,
              receipt.modelID == report.model.id,
              receipt.revision == report.model.revision,
              receipt.environmentFingerprint == environmentFingerprint(report.environment)
        else { return report }

        report.verificationReceipt = receipt
        merge(receipt, into: &report)
        return report
    }

    public static func environmentFingerprint(
        _ environment: ModelCheckReport.EnvironmentSection
    ) -> String {
        [environment.chip, environment.arch, String(environment.ramBytes),
         environment.macOSVersion]
            .joined(separator: "|")
    }

    private static func deriveOperations(
        _ report: ModelCheckReport,
        hasHFAccess: Bool
    ) -> [ModelCheckReport.OperationAssessment] {
        let inspected = hasRepositoryEvidence(report)
        let loadStatus: ModelCheckReport.OperationStatus
        switch report.checkedPath.status {
        case .expectedToWork: loadStatus = .supported
        case .changesRequired:
            let unresolved = report.requiredChanges.filter {
                !($0.kind == "access" && hasHFAccess)
            }
            loadStatus = unresolved.isEmpty ? .supported : .blocked
        case .unsupportedOnCheckedPath: loadStatus = .blocked
        case .unknown: loadStatus = .unverified
        }

        let downloadStatus: ModelCheckReport.OperationStatus
        let downloadDetail: String
        if report.model.gated && !hasHFAccess {
            downloadStatus = .blocked
            downloadDetail = "Gated repository; accept its license and provide HF_TOKEN before downloading weights."
        } else if inspected {
            downloadStatus = .supported
            downloadDetail = "Repository metadata exposes a downloadable revision; weights were not fetched by model-check."
        } else {
            downloadStatus = .unverified
            downloadDetail = "Repository access was not established, so downloadability is unknown."
        }

        let inferenceStatus = loadStatus
        let inferenceDetail: String
        switch inferenceStatus {
        case .supported:
            inferenceDetail = "Static checks predict bounded inference can run; no sample has been measured on this device."
        case .blocked:
            inferenceDetail = "Inference is blocked by the checked load/runtime path: \(report.checkedPath.detail)"
        case .unverified:
            inferenceDetail = "The checker lacks enough architecture/runtime evidence to predict inference."
        case .verifiedOnThisDevice:
            inferenceDetail = "Measured receipt available."
        }

        let loraStatus: ModelCheckReport.OperationStatus
        let loraDetail: String
        if loadStatus == .blocked {
            loraStatus = .blocked
            loraDetail = "LoRA/SFT requires a loadable base model; the checked load path is blocked."
        } else if report.model.formats.contains("peft-adapter") {
            loraStatus = .blocked
            loraDetail = "This repository is an adapter, not a standalone base for LoRA/SFT."
        } else if loadStatus == .supported && report.model.formats.contains("safetensors") {
            loraStatus = .supported
            loraDetail = "The checked safetensors base is structurally eligible for the native LoRA/SFT path; no training step was run."
        } else {
            loraStatus = .unverified
            loraDetail = "Training compatibility is not established for this format/runtime combination."
        }

        let agenticStatus: ModelCheckReport.OperationStatus = inferenceStatus == .blocked ? .blocked : .unverified
        let agenticDetail = agenticStatus == .blocked
            ? "Agentic use requires working inference; the checked inference path is blocked."
            : "Model-check does not execute a tool-call/template/parser task, so agentic behavior remains unverified."

        return [
            .init(operation: .inspect, status: inspected ? .supported : .unverified,
                  detail: inspected
                      ? "Hub metadata/config evidence was inspected without downloading weights."
                      : "Repository metadata could not be established."),
            .init(operation: .download, status: downloadStatus, detail: downloadDetail),
            .init(operation: .load, status: loadStatus, detail: report.checkedPath.detail),
            .init(operation: .inference, status: inferenceStatus, detail: inferenceDetail),
            .init(operation: .loraSFT, status: loraStatus, detail: loraDetail),
            .init(operation: .agenticUse, status: agenticStatus, detail: agenticDetail),
        ]
    }

    private static func deriveStages(
        _ report: ModelCheckReport
    ) -> [ModelCheckReport.ExecutionStage] {
        let operations = report.operations ?? []
        let inspect = operations.first { $0.operation == .inspect }
        let download = operations.first { $0.operation == .download }
        let load = operations.first { $0.operation == .load }

        guard inspect?.status != .unverified else {
            return stageSequence(failure: .inspect, status: .failed,
                                 detail: inspect?.detail ?? "Repository inspection did not complete.")
        }

        var stages: [ModelCheckReport.ExecutionStage] = [
            .init(stage: .inspect, status: .passed,
                  detail: "Repository metadata/config inspection completed."),
            .init(stage: .validate, status: .passed,
                  detail: "Static compatibility rules completed; this is prediction evidence, not a run receipt."),
        ]
        if download?.status == .blocked {
            stages.append(.init(stage: .download, status: .blocked,
                                detail: download?.detail ?? "Download is blocked."))
            stages += pendingStages(after: .download, blocked: true)
            return stages
        }
        stages.append(.init(stage: .download, status: .pending,
                            detail: "model-check never downloads weights."))
        if load?.status == .blocked {
            stages.append(.init(stage: .load, status: .blocked,
                                detail: load?.detail ?? "The checked load path is blocked."))
            stages += pendingStages(after: .load, blocked: true)
            return stages
        }
        stages.append(.init(stage: .load, status: .pending,
                            detail: "No model load has been measured on this device."))
        stages += pendingStages(after: .load, blocked: false)
        return stages
    }

    private static func merge(
        _ receipt: ModelCheckReport.VerificationReceipt,
        into report: inout ModelCheckReport
    ) {
        if receipt.status == .verified {
            updateOperation(.download, status: .verifiedOnThisDevice,
                            detail: receiptDetail(receipt, action: "download/access completed"),
                            in: &report)
            updateOperation(.load, status: .verifiedOnThisDevice,
                            detail: receiptDetail(receipt, action: "model loaded"),
                            in: &report)
            updateOperation(.inference, status: .verifiedOnThisDevice,
                            detail: receiptDetail(receipt, action: sampleDetail(receipt)),
                            in: &report)
            report.executionStages = ModelCheckReport.ExecutionStageName.allCases.map {
                .init(stage: $0, status: .passed,
                      detail: $0 == .ready
                          ? receiptDetail(receipt, action: "bounded smoke run reached ready")
                          : "Completed during the measured model-run receipt.")
            }
            return
        }

        let failedAt = receipt.failureStage ?? .load
        let stageStatus: ModelCheckReport.ExecutionStageStatus = receipt.status == .blocked ? .blocked : .failed
        report.executionStages = stageSequence(
            failure: failedAt, status: stageStatus,
            detail: receiptDetail(receipt, action: "execution stopped at \(failedAt.displayName)"))

        switch failedAt {
        case .inspect, .validate:
            break
        case .download:
            updateOperation(.download, status: .blocked,
                            detail: receiptDetail(receipt, action: "download failed or was blocked"),
                            in: &report)
            updateOperation(.load, status: .blocked,
                            detail: "Load was not reached because download did not complete.", in: &report)
            updateOperation(.inference, status: .blocked,
                            detail: "Inference was not reached because download did not complete.", in: &report)
        case .load:
            updateOperation(.load, status: .blocked,
                            detail: receiptDetail(receipt, action: "all attempted load paths failed"),
                            in: &report)
            updateOperation(.inference, status: .blocked,
                            detail: "Inference was not reached because all attempted load paths failed.", in: &report)
        case .warmUp, .smokeTest, .ready:
            updateOperation(.load, status: .verifiedOnThisDevice,
                            detail: receiptDetail(receipt, action: "model loaded before the later-stage failure"),
                            in: &report)
            updateOperation(.inference, status: .blocked,
                            detail: receiptDetail(receipt, action: "bounded inference did not reach ready"),
                            in: &report)
        }
    }

    private static func hasRepositoryEvidence(_ report: ModelCheckReport) -> Bool {
        report.evidence.contains { $0.source.contains("huggingface.co") }
            || !report.model.formats.isEmpty
            || !report.model.architectures.isEmpty
    }

    private static func updateOperation(
        _ operation: ModelCheckReport.Operation,
        status: ModelCheckReport.OperationStatus,
        detail: String,
        in report: inout ModelCheckReport
    ) {
        guard let index = report.operations?.firstIndex(where: { $0.operation == operation }) else { return }
        report.operations?[index].status = status
        report.operations?[index].detail = detail
    }

    private static func sampleDetail(_ receipt: ModelCheckReport.VerificationReceipt) -> String {
        guard let attempt = receipt.attempts.last(where: { $0.status == .verified }) else {
            return "bounded inference completed"
        }
        if let generated = attempt.generatedTokens {
            return "bounded inference generated \(generated) measured tokens in \(attempt.durationMS) ms"
        }
        return "bounded inference produced \(attempt.outputCharacters) characters in \(attempt.durationMS) ms; this runtime did not expose an exact token count"
    }

    private static func receiptDetail(
        _ receipt: ModelCheckReport.VerificationReceipt,
        action: String
    ) -> String {
        let runtime = receipt.runtime.map { " via \($0)" } ?? ""
        return "Measured \(receipt.verifiedAt)\(runtime): \(action)."
    }

    private static func stageSequence(
        failure: ModelCheckReport.ExecutionStageName,
        status: ModelCheckReport.ExecutionStageStatus,
        detail: String
    ) -> [ModelCheckReport.ExecutionStage] {
        let stages = ModelCheckReport.ExecutionStageName.allCases
        guard let failureIndex = stages.firstIndex(of: failure) else { return [] }
        return stages.enumerated().map { index, stage in
            if index < failureIndex {
                return .init(stage: stage, status: .passed,
                             detail: "Completed before the recorded \(failure.displayName) boundary.")
            }
            if index == failureIndex {
                return .init(stage: stage, status: status, detail: detail)
            }
            return .init(stage: stage, status: .blocked,
                         detail: "Not reached because \(failure.displayName) did not complete.")
        }
    }

    private static func pendingStages(
        after stage: ModelCheckReport.ExecutionStageName,
        blocked: Bool
    ) -> [ModelCheckReport.ExecutionStage] {
        guard let index = ModelCheckReport.ExecutionStageName.allCases.firstIndex(of: stage) else { return [] }
        return ModelCheckReport.ExecutionStageName.allCases.dropFirst(index + 1).map {
            .init(stage: $0, status: blocked ? .blocked : .pending,
                  detail: blocked
                      ? "Not reachable until the earlier blocker is resolved."
                      : "Requires a bounded model-run receipt.")
        }
    }
}

/// Local, atomic receipt storage. The report content carries the authoritative
/// model/revision/device identity, so a filename collision cannot cause a
/// receipt to be accepted for the wrong target.
public struct ModelVerificationStore: Sendable {
    public let directory: URL

    public init(directory: URL? = nil) {
        if let directory {
            self.directory = directory
        } else if let override = ProcessInfo.processInfo.environment["POSTTRAINLLM_MODEL_RECEIPTS_DIR"],
                  !override.isEmpty {
            self.directory = URL(fileURLWithPath: override, isDirectory: true)
        } else {
            self.directory = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".cache/posttrainllm/model-check-receipts", isDirectory: true)
        }
    }

    public func load(
        modelID: String,
        revision: String,
        environment: ModelCheckReport.EnvironmentSection
    ) -> ModelCheckReport.VerificationReceipt? {
        let url = receiptURL(modelID: modelID, revision: revision)
        guard let data = try? Data(contentsOf: url),
              let receipt = try? JSONDecoder().decode(ModelCheckReport.VerificationReceipt.self, from: data),
              receipt.schemaVersion == 1,
              receipt.modelID == modelID,
              receipt.revision == revision,
              receipt.environmentFingerprint == ModelCompatibilityContract.environmentFingerprint(environment)
        else { return nil }
        return receipt
    }

    @discardableResult
    public func write(
        _ source: ModelCheckReport.VerificationReceipt
    ) throws -> URL {
        let receipt = Self.sanitized(source)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let url = receiptURL(modelID: receipt.modelID, revision: receipt.revision)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        try encoder.encode(receipt).write(to: url, options: .atomic)
        return url
    }

    public static func sanitizedStderr(_ source: String?, limit: Int = 8_192) -> String? {
        guard var value = source?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        let patterns = [
            #"(?i)hf_[a-z0-9]{8,}"#,
            #"(?i)bearer\s+[^\s\"']+"#,
            #"(?i)(token|password|secret|api[_-]?key)=([^\s&]+)"#,
            #"https://[^/@\s:]+:[^/@\s]+@"#,
        ]
        for pattern in patterns {
            guard let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            let range = NSRange(value.startIndex..<value.endIndex, in: value)
            value = regex.stringByReplacingMatches(in: value, range: range, withTemplate: "[REDACTED]")
        }
        if value.count > limit {
            value = String(value.prefix(limit)) + "\n…[truncated]"
        }
        return value
    }

    private static func sanitized(
        _ source: ModelCheckReport.VerificationReceipt
    ) -> ModelCheckReport.VerificationReceipt {
        var receipt = source
        receipt.attempts = source.attempts.map { attempt in
            var cleaned = attempt
            cleaned.stderr = sanitizedStderr(attempt.stderr)
            return cleaned
        }
        return receipt
    }

    private func receiptURL(modelID: String, revision: String) -> URL {
        let key = modelID + "@" + revision
        let prefix = key.unicodeScalars.map { scalar -> Character in
            CharacterSet.alphanumerics.contains(scalar) || "-_.".unicodeScalars.contains(scalar)
                ? Character(String(scalar)) : "_"
        }
        let readable = String(prefix.prefix(80))
        return directory.appendingPathComponent("\(readable)-\(Self.fnv1a(key)).json")
    }

    private static func fnv1a(_ value: String) -> String {
        var hash: UInt64 = 14_695_981_039_346_656_037
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash &*= 1_099_511_628_211
        }
        return String(hash, radix: 16)
    }
}
