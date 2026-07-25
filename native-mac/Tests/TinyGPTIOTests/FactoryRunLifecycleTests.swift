import Foundation
import XCTest
@testable import TinyGPTIO

final class FactoryRunLifecycleTests: XCTestCase {
    private let baseDate = ISO8601DateFormatter().date(
        from: "2026-07-25T00:00:00Z"
    )!

    private func temporaryDirectory(_ name: String = UUID().uuidString) throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("factory-run-lifecycle-tests")
            .appendingPathComponent(name)
        try FileManager.default.createDirectory(at: root,
                                                withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        return root
    }

    private func makeRun(root: URL,
                         id: String = "fixture-run",
                         now: Date? = nil) throws -> URL {
        let run = root.appendingPathComponent(id)
        try FileManager.default.createDirectory(at: run,
                                                withIntermediateDirectories: true)
        let config = FactoryRun.Config(
            runId: id,
            target: "fixture",
            ownerGoal: "Exercise lifecycle metadata without model work.",
            baseModel: .init(id: "fixture-base"),
            candidate: .init(method: "metadata-only"),
            eval: .init(primary: "fixture-gate")
        )
        try FactoryRunFolder.writeJSON(
            config,
            to: run.appendingPathComponent(FactoryRunFolder.configFile)
        )
        if let now {
            _ = try FactoryRunLifecycle.initialize(directory: run, now: now)
        }
        return run
    }

    private func writeDecision(_ run: URL) throws {
        try FactoryRunFolder.writeJSON(
            FactoryRun.DecisionRecord(
                decision: .retryTraining,
                reason: "Fixture requires another run."
            ),
            to: run.appendingPathComponent(FactoryRunFolder.decisionFile)
        )
    }

    private func transition(_ status: FactoryRunLifecycle.Status,
                            run: URL,
                            to phase: FactoryRunLifecycle.Phase,
                            reason: String? = nil,
                            now: Date? = nil) throws -> FactoryRunLifecycle.Status {
        try FactoryRunLifecycle.transition(
            directory: run,
            to: phase,
            expectedRevision: status.revision,
            source: "test",
            command: "factory-run transition",
            reason: reason,
            now: now ?? baseDate.addingTimeInterval(Double(status.revision))
        )
    }

    private func fixtureURL(_ path: String) throws -> URL {
        #if SWIFT_PACKAGE
        let resourceBundle = Bundle.module
        #else
        let resourceBundle = Bundle.main
        #endif
        guard let resourceURL = resourceBundle.resourceURL else {
            throw XCTSkip("missing test resource root")
        }
        let url = resourceURL.appendingPathComponent("Fixtures/FactoryRunLifecycle")
            .appendingPathComponent(path)
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw XCTSkip("missing fixture \(path)")
        }
        return url
    }

    private func copyFixtureDirectory(_ name: String, to root: URL) throws -> URL {
        let source = try fixtureURL(name)
        let destination = root.appendingPathComponent(name)
        try FileManager.default.copyItem(at: source, to: destination)
        return destination
    }

    func test_statusFixturesCoverRequiredShapes() throws {
        for name in [
            "status-normal.json",
            "status-report-only.json",
            "status-evaluation-only.json",
            "status-imported.json",
            "status-failed.json",
            "status-terminal.json",
        ] {
            let status = try FactoryRun.decode(
                FactoryRunLifecycle.Status.self,
                from: Data(contentsOf: try fixtureURL(name))
            )
            XCTAssertNoThrow(try FactoryRunLifecycle.validate(status), name)
        }
        XCTAssertThrowsError(
            try FactoryRun.decode(
                FactoryRunLifecycle.Status.self,
                from: Data(contentsOf: try fixtureURL("status-malformed.json"))
            )
        )
    }

    func test_normalTransitionGraphAndDecisionBoundary() throws {
        let root = try temporaryDirectory()
        let run = try makeRun(root: root)
        var status = try FactoryRunLifecycle.initialize(directory: run, now: baseDate)
        for phase in [
            FactoryRunLifecycle.Phase.dataReady,
            .training, .trained, .evaluating, .evaluated,
            .packaging, .packaged, .reporting,
        ] {
            status = try transition(status, run: run, to: phase)
        }

        XCTAssertThrowsError(
            try transition(status, run: run, to: .decided)
        ) { error in
            XCTAssertEqual(error as? FactoryRunLifecycle.LifecycleError,
                           .decisionRequired)
        }
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).revision, 9)

        try writeDecision(run)
        status = try transition(status, run: run, to: .decided)
        XCTAssertEqual(status.phase, .decided)
        XCTAssertEqual(status.revision, 10)
        XCTAssertThrowsError(
            try FactoryRunLifecycle.transition(
                directory: run,
                to: .failed,
                expectedRevision: status.revision,
                failure: .init(code: "retry", summary: "Retry requested.")
            )
        ) { error in
            XCTAssertEqual(error as? FactoryRunLifecycle.LifecycleError,
                           .terminalState(.decided))
        }
    }

    func test_alternateEdgesRequireMachineReadableReasons() throws {
        let root = try temporaryDirectory()
        let reportRun = try makeRun(root: root, id: "report-only")
        let created = try FactoryRunLifecycle.initialize(
            directory: reportRun,
            parentRunId: "prior-run",
            now: baseDate
        )
        XCTAssertThrowsError(
            try transition(created, run: reportRun, to: .reporting)
        ) { error in
            XCTAssertEqual(error as? FactoryRunLifecycle.LifecycleError,
                           .alternateReasonRequired(from: .created, to: .reporting))
        }
        let reporting = try FactoryRunLifecycle.transition(
            directory: reportRun,
            to: .reporting,
            expectedRevision: created.revision,
            source: "test",
            command: "factory-run transition",
            reason: "report-only",
            successorRunId: "planned-successor",
            now: baseDate.addingTimeInterval(1)
        )
        XCTAssertEqual(reporting.lastTransition.reason, "report-only")
        XCTAssertEqual(reporting.parentRunId, "prior-run")
        XCTAssertEqual(reporting.successorRunId, "planned-successor")
        XCTAssertThrowsError(
            try transition(reporting, run: reportRun, to: .dataReady)
        ) { error in
            XCTAssertEqual(error as? FactoryRunLifecycle.LifecycleError,
                           .invalidTransition(from: .reporting, to: .dataReady))
        }

        let evalRun = try makeRun(root: root, id: "evaluation-only")
        var evaluation = try FactoryRunLifecycle.initialize(
            directory: evalRun, now: baseDate.addingTimeInterval(10)
        )
        evaluation = try transition(
            evaluation,
            run: evalRun,
            to: .evaluating,
            reason: "evaluation-only"
        )
        evaluation = try transition(evaluation, run: evalRun, to: .evaluated)
        XCTAssertEqual(evaluation.phase, .evaluated)
    }

    func test_everyDocumentedAlternateEdge() throws {
        let root = try temporaryDirectory()
        let cases: [(String, [FactoryRunLifecycle.Phase],
                     FactoryRunLifecycle.Phase)] = [
            ("created-evaluating", [], .evaluating),
            ("created-reporting", [], .reporting),
            ("ready-evaluating", [.dataReady], .evaluating),
            ("ready-reporting", [.dataReady], .reporting),
            ("trained-reporting", [.dataReady, .training, .trained], .reporting),
            ("evaluated-reporting",
             [.dataReady, .training, .trained, .evaluating, .evaluated],
             .reporting),
        ]
        for (name, setup, target) in cases {
            let run = try makeRun(root: root, id: name)
            var status = try FactoryRunLifecycle.initialize(
                directory: run, now: baseDate
            )
            for phase in setup {
                status = try transition(status, run: run, to: phase)
            }
            status = try transition(
                status,
                run: run,
                to: target,
                reason: "documented-skip"
            )
            XCTAssertEqual(status.phase, target, name)
        }
    }

    func test_identityAndPrivateFailureValidationFailClosed() throws {
        let root = try temporaryDirectory()
        let run = try makeRun(root: root)
        let status = try FactoryRunLifecycle.initialize(directory: run, now: baseDate)
        let mismatched = FactoryRun.Config(
            runId: "different-run",
            target: "fixture",
            ownerGoal: "Mismatch",
            baseModel: .init(id: "fixture-base"),
            candidate: .init(method: "metadata-only"),
            eval: .init(primary: "fixture-gate")
        )
        try FactoryRunFolder.writeJSON(
            mismatched,
            to: run.appendingPathComponent(FactoryRunFolder.configFile)
        )
        XCTAssertThrowsError(try FactoryRunLifecycle.readStatus(directory: run)) {
            XCTAssertEqual(
                $0 as? FactoryRunLifecycle.LifecycleError,
                .identityMismatch(status: status.runId, config: "different-run")
            )
        }

        XCTAssertThrowsError(
            try FactoryRunLifecycle.validate(
                FactoryRunLifecycle.Failure(
                    code: "unsafe code",
                    summary: String(repeating: "x", count: 241)
                )
            )
        )
        XCTAssertThrowsError(
            try FactoryRunLifecycle.validate(
                FactoryRunLifecycle.Failure(
                    code: "unsafe-output",
                    summary: "Raw prompt content was copied here."
                )
            )
        )

        try FactoryRunFolder.writeJSON(
            FactoryRun.Config(
                runId: status.runId,
                target: "fixture",
                ownerGoal: "Restored",
                baseModel: .init(id: "fixture-base"),
                candidate: .init(method: "metadata-only"),
                eval: .init(primary: "fixture-gate")
            ),
            to: run.appendingPathComponent(FactoryRunFolder.configFile)
        )
        var object = try JSONSerialization.jsonObject(
            with: FactoryRun.encode(status)
        ) as! [String: Any]
        object["prompt_text"] = "must never be accepted"
        try JSONSerialization.data(withJSONObject: object).write(
            to: run.appendingPathComponent(FactoryRunLifecycle.statusFile)
        )
        XCTAssertThrowsError(try FactoryRunLifecycle.readStatus(directory: run)) {
            XCTAssertEqual($0 as? FactoryRunLifecycle.LifecycleError,
                           .privateField("prompt_text"))
        }
    }

    func test_expectedRevisionAndRacingWritersAllowOneCommit() throws {
        let root = try temporaryDirectory()
        let run = try makeRun(root: root)
        let status = try FactoryRunLifecycle.initialize(directory: run, now: baseDate)
        let preview = try FactoryRunLifecycle.transition(
            directory: run,
            to: .dataReady,
            expectedRevision: status.revision,
            source: "preview",
            command: "factory-run transition",
            dryRun: true
        )
        XCTAssertEqual(preview.revision, 2)
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).revision, 1)
        let group = DispatchGroup()
        let queue = DispatchQueue(label: "lifecycle-race", attributes: .concurrent)
        let resultLock = NSLock()
        var successes = 0
        var failures: [Error] = []
        for offset in 1...2 {
            group.enter()
            queue.async {
                defer { group.leave() }
                do {
                    _ = try FactoryRunLifecycle.transition(
                        directory: run,
                        to: .dataReady,
                        expectedRevision: status.revision,
                        source: "race",
                        command: "race-\(offset)",
                        now: self.baseDate.addingTimeInterval(Double(offset))
                    )
                    resultLock.lock()
                    successes += 1
                    resultLock.unlock()
                } catch {
                    resultLock.lock()
                    failures.append(error)
                    resultLock.unlock()
                }
            }
        }
        group.wait()
        XCTAssertEqual(successes, 1)
        XCTAssertEqual(failures.count, 1)
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).revision, 2)
        XCTAssertTrue(failures.contains {
            $0 is FactoryRunLifecycle.LifecycleError
        })

        XCTAssertThrowsError(
            try FactoryRunLifecycle.transition(
                directory: run,
                to: .training,
                expectedRevision: 1
            )
        ) { error in
            XCTAssertEqual(error as? FactoryRunLifecycle.LifecycleError,
                           .staleRevision(expected: 1, actual: 2))
        }
    }

    func test_pointerValidationSelectionAndPathEscape() throws {
        let root = try temporaryDirectory()
        _ = try makeRun(root: root, id: "older", now: baseDate)
        _ = try makeRun(
            root: root,
            id: "newer",
            now: baseDate.addingTimeInterval(60)
        )
        let current = try XCTUnwrap(
            FactoryRunLifecycle.validatedPointer(
                root: root,
                fileName: FactoryRunLifecycle.currentPointerFile
            )
        )
        XCTAssertEqual(current.runId, "newer")

        var drifted = try JSONSerialization.jsonObject(
            with: FactoryRun.encode(current)
        ) as! [String: Any]
        drifted["lifecycle_revision"] = 99
        try JSONSerialization.data(withJSONObject: drifted).write(
            to: root.appendingPathComponent(FactoryRunLifecycle.currentPointerFile)
        )
        XCTAssertThrowsError(
            try FactoryRunLifecycle.validatedPointer(
                root: root,
                fileName: FactoryRunLifecycle.currentPointerFile
            )
        ) {
            XCTAssertEqual(
                $0 as? FactoryRunLifecycle.LifecycleError,
                .pointerMismatch("current-run.json disagrees with run-status.json")
            )
        }
        _ = try FactoryRunLifecycle.reconcile(root: root, write: true)

        let escaped: [String: Any] = [
            "schema_version": 1,
            "relative_run_path": "../outside",
            "run_id": "outside",
            "lifecycle_revision": 1,
            "phase": "created",
            "updated_at": "2026-07-25T00:00:00Z",
        ]
        try JSONSerialization.data(
            withJSONObject: escaped,
            options: [.prettyPrinted]
        ).write(to: root.appendingPathComponent(FactoryRunLifecycle.currentPointerFile))
        XCTAssertThrowsError(
            try FactoryRunLifecycle.validatedPointer(
                root: root,
                fileName: FactoryRunLifecycle.currentPointerFile
            )
        ) {
            XCTAssertEqual($0 as? FactoryRunLifecycle.LifecycleError,
                           .pathEscapesRoot("../outside"))
        }
        let repaired = try FactoryRunLifecycle.reconcile(root: root, write: true)
        XCTAssertTrue(repaired.repairs.contains("rebuilt current-run.json"))
        XCTAssertEqual(
            try FactoryRunLifecycle.validatedPointer(
                root: root,
                fileName: FactoryRunLifecycle.currentPointerFile
            )?.runId,
            "newer"
        )
    }

    func test_reconcileCleansInterruptedWritesAndStaleLocksIdempotently() throws {
        let root = try temporaryDirectory()
        let run = try makeRun(root: root, now: baseDate)
        let temporary = run.appendingPathComponent(".run-status.abandoned.tmp")
        try Data("partial".utf8).write(to: temporary)
        let lock = run.appendingPathComponent(FactoryRunLifecycle.lockDirectory)
        try FileManager.default.createDirectory(at: lock,
                                                withIntermediateDirectories: false)
        let owner: [String: Any] = [
            "pid": 999_999,
            "acquired_at": "2026-07-20T00:00:00Z",
        ]
        try JSONSerialization.data(withJSONObject: owner).write(
            to: lock.appendingPathComponent(FactoryRunLifecycle.lockOwnerFile)
        )
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).phase,
                       .created)

        let now = baseDate.addingTimeInterval(2 * FactoryRunLifecycle.staleAfter)
        let preview = try FactoryRunLifecycle.reconcile(root: root, now: now)
        XCTAssertTrue(preview.dryRun)
        XCTAssertTrue(preview.diagnostics.contains { $0.kind == "stale-lock" })
        XCTAssertTrue(preview.diagnostics.contains {
            $0.kind == "abandoned-temporary"
        })
        XCTAssertTrue(FileManager.default.fileExists(atPath: temporary.path))

        let written = try FactoryRunLifecycle.reconcile(
            root: root, write: true, now: now
        )
        XCTAssertFalse(written.repairs.isEmpty)
        XCTAssertFalse(FileManager.default.fileExists(atPath: temporary.path))
        XCTAssertNil(FactoryRunLifecycle.lockDiagnostic(directory: run, now: now))
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).phase,
                       .created)

        let second = try FactoryRunLifecycle.reconcile(
            root: root, write: true, now: now
        )
        XCTAssertTrue(second.diagnostics.isEmpty)
        XCTAssertTrue(second.repairs.isEmpty)
    }

    func test_staleActiveRunRemainsActiveWithWarning() throws {
        let root = try temporaryDirectory()
        let run = try makeRun(root: root, now: baseDate)
        let records = try FactoryRunLifecycle.list(
            root: root,
            filter: .stale,
            now: baseDate.addingTimeInterval(FactoryRunLifecycle.staleAfter + 1)
        )
        XCTAssertEqual(records.count, 1)
        XCTAssertTrue(records[0].isStale)
        _ = try FactoryRunLifecycle.reconcile(
            root: root,
            write: true,
            now: baseDate.addingTimeInterval(FactoryRunLifecycle.staleAfter + 1)
        )
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).phase,
                       .created)
        let current = try FactoryRunLifecycle.readStatus(directory: run)
        _ = try FactoryRunLifecycle.transition(
            directory: run,
            to: .failed,
            expectedRevision: current.revision,
            source: "test",
            command: "factory-run transition",
            failure: .init(code: "operator-stop",
                           summary: "Operator explicitly stopped the stale run.")
        )
        XCTAssertEqual(try FactoryRunLifecycle.list(root: root, filter: .failed).count, 1)
        XCTAssertEqual(try FactoryRunLifecycle.list(root: root, filter: .terminal).count, 1)
    }

    func test_legacyImportsRecordOnlyProvenEvidence() throws {
        let root = try temporaryDirectory()
        let expected: [(String, FactoryRunLifecycle.Phase, [String])] = [
            ("legacy-complete", .decided, ["decision.json"]),
            ("legacy-report-only", .reporting, ["report.md"]),
            ("legacy-partial", .dataReady, ["dataset.json"]),
        ]
        for (name, phase, evidence) in expected {
            let run = try copyFixtureDirectory(name, to: root)
            XCTAssertNil(try FactoryRunFolder.readLifecycle(from: run))
            let imported = try FactoryRunLifecycle.importLegacy(
                directory: run,
                source: "test",
                now: baseDate
            )
            XCTAssertEqual(imported.phase, phase)
            XCTAssertTrue(imported.imported)
            for item in evidence {
                XCTAssertTrue(imported.importEvidence.contains(item), "\(name): \(item)")
            }
        }
        XCTAssertEqual(
            try FactoryRunLifecycle.list(root: root, filter: .imported).count,
            3
        )

        let invalid = try copyFixtureDirectory("legacy-invalid", to: root)
        XCTAssertThrowsError(
            try FactoryRunLifecycle.importLegacy(directory: invalid, source: "test")
        )
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: invalid.appendingPathComponent(
                FactoryRunLifecycle.statusFile
            ).path
        ))
    }

    func test_folderWriteCreatesLifecycleButLegacyValidationRemainsCompatible() throws {
        let root = try temporaryDirectory()
        let directory = root.appendingPathComponent("new-folder")
        let bundle = FactoryRun.Bundle(
            config: .init(
                runId: "new-folder",
                target: "fixture",
                ownerGoal: "Exercise lifecycle-integrated rendering.",
                baseModel: .init(id: "fixture-base"),
                candidate: .init(method: "metadata-only"),
                eval: .init(primary: "fixture-gate")
            ),
            dataset: .init(
                datasetId: "fixture-data",
                sources: [.init(kind: "fixture", path: "fixture.jsonl", rows: 1)]
            ),
            baseline: .init(modelId: "base", suite: "fixture-gate", score: 0.5),
            candidate: .init(modelId: "candidate", suite: "fixture-gate", score: 0.6),
            decision: .init(
                decision: .retryTraining,
                reason: "Fixture remains retry-only."
            )
        )
        try FactoryRunFolder.write(bundle, to: directory)
        XCTAssertEqual(
            try FactoryRunFolder.readLifecycle(from: directory)?.phase,
            .decided
        )
        XCTAssertEqual(
            try FactoryRunLifecycle.validatedPointer(
                root: root,
                fileName: FactoryRunLifecycle.latestPointerFile
            )?.runId,
            "new-folder"
        )
        XCTAssertNoThrow(try FactoryRunFolder.validate(directory: directory))

        let configBeforeRejectedRewrite = try Data(
            contentsOf: directory.appendingPathComponent(FactoryRunFolder.configFile)
        )
        let replacement = FactoryRun.Bundle(
            config: .init(
                runId: "new-folder",
                target: "fixture",
                ownerGoal: "This terminal run must not be rewritten.",
                baseModel: .init(id: "fixture-base"),
                candidate: .init(method: "metadata-only"),
                eval: .init(primary: "fixture-gate")
            ),
            dataset: bundle.dataset,
            baseline: bundle.baseline,
            candidate: bundle.candidate,
            decision: bundle.decision
        )
        XCTAssertThrowsError(try FactoryRunFolder.write(replacement, to: directory)) {
            XCTAssertEqual(
                $0 as? FactoryRunLifecycle.LifecycleError,
                .terminalState(.decided)
            )
        }
        XCTAssertEqual(
            try Data(
                contentsOf: directory.appendingPathComponent(FactoryRunFolder.configFile)
            ),
            configBeforeRejectedRewrite
        )

        let legacy = try copyFixtureDirectory("legacy-complete", to: root)
        XCTAssertNil(try FactoryRunFolder.readLifecycle(from: legacy))
        XCTAssertNoThrow(try FactoryRunFolder.validate(directory: legacy))
    }
}
