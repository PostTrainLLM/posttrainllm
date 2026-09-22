import Foundation
import TinyGPTCheck

/// Runner selection for `posttrainllm model-run` (issue #157) — pure
/// functions over the model-check report so the policy is unit-testable
/// without spawning anything.
///
/// A *runner* is an installed piece of software that can turn a Hub repo
/// into generated tokens:
///   native   — posttrainllm's own hf-load (always available: it is us)
///   mlx-swift— the `posttrainllm-mlxrun` sibling executable: Apple's
///              MLX-Swift-LM impls in-process, no python dependency —
///              the preferred alternative when native can't run an arch
///   mlx-lm   — `python3 -m mlx_lm generate` (wider arch table still;
///              depends on a healthy python env)
///   ollama   — `ollama run hf.co/<id>` (pulls + runs GGUF in one step),
///              with a direct-download + `ollama create` fallback for
///              Hub Xet-redirect failures
///   lms      — LM Studio CLI (`lms get` + `lms load` + `lms chat -p`),
///              the GGUF fallback when Ollama is absent or can't pull
///   llamaCpp — `llama-cli -hf <id>:<quant>` — pulls + generates direct
///              from the Hub, the last-resort GGUF runner
///
/// GGUF is deliberately *not* routed to native: `gguf-load` is a
/// structural validator — it parses and maps tensors but cannot generate
/// (tokenizer extraction is an open follow-up). Claiming a "run" from it
/// would be dishonest.
///
/// Order encodes preference. When the checked path cleared, native runs
/// first because model-run exists to *verify* the checker's prediction —
/// a real load is the evidence. Installed alternatives follow so a
/// detected-but-broken runtime falls through instead of dead-ending.
public enum Runner: String, Sendable, CaseIterable {
    case native
    case mlxSwift = "mlx-swift"
    case mlxLm = "mlx-lm"
    case ollama
    case lms
    case llamaCpp = "llama-cli"
}

public struct RunnerPlan: Equatable, Sendable {
    public let runner: Runner
    public let why: String
    public init(runner: Runner, why: String) {
        self.runner = runner
        self.why = why
    }
}

public enum RunnerPlanner {

    private struct Availability {
        let ollama: Bool
        let lms: Bool
        let llamaCpp: Bool
        let mlxSwift: Bool
        let mlxLm: Bool

        init(_ probes: [ModelCheckReport.RuntimeProbe]) {
            ollama = installed(probes, "ollama")
            lms = installed(probes, "lms (LM Studio)")
            llamaCpp = installed(probes, "llama.cpp")
            mlxSwift = installed(probes, "mlx-swift runner")
            mlxLm = probes.contains {
                $0.name == "python3 ML stack" && $0.found
                    && ($0.version?.contains("mlx-lm") ?? false)
            }
        }
    }

    /// Ordered runner candidates for this report on this machine.
    /// `forced` (from `--runtime`) narrows to a single candidate; an
    /// unavailable forced runner yields an empty list and `blocker`
    /// explains it. Native needs no probe — the running binary is it.
    public static func plans(for report: ModelCheckReport,
                             forced: Runner? = nil) -> [RunnerPlan] {
        let available = Availability(report.environment.runtimes)
        let fmts = Set(report.model.formats)
        // The checked path is the native runtime; only a green/amber
        // assessment justifies downloading GBs for a real load. Unknown
        // or unsupported stays off native — a wrong-architecture load can
        // fail silently (builds the wrong model), which is worse than a
        // clear refusal.
        let checkedOK = report.checkedPath.status == .expectedToWork
        let isMainRevision = report.model.revision == "main"
        let exactGGUF = report.model.filePath?.lowercased().hasSuffix(".gguf") == true

        if let forced {
            return forcedPlan(
                forced, formats: fmts, checkedOK: checkedOK,
                isMainRevision: isMainRevision, exactGGUF: exactGGUF,
                available: available)
        }

        return safetensorPlans(
            formats: fmts, checkedOK: checkedOK,
            isMainRevision: isMainRevision, available: available)
            + ggufPlans(
                formats: fmts, isMainRevision: isMainRevision,
                exactGGUF: exactGGUF, availability: available)
    }

    private static func forcedPlan(
        _ runner: Runner, formats: Set<String>, checkedOK: Bool,
        isMainRevision: Bool, exactGGUF: Bool,
        available: Availability
    ) -> [RunnerPlan] {
        let usable: Bool
        switch runner {
        case .native: usable = formats.contains("safetensors") && checkedOK
        case .mlxSwift: usable = available.mlxSwift
        case .mlxLm: usable = available.mlxLm && isMainRevision
        case .ollama: usable = available.ollama && isMainRevision && !exactGGUF
        case .lms: usable = available.lms
        case .llamaCpp: usable = available.llamaCpp && isMainRevision && !exactGGUF
        }
        return usable ? [RunnerPlan(runner: runner, why: "forced via --runtime")] : []
    }

    private static func safetensorPlans(
        formats: Set<String>, checkedOK: Bool, isMainRevision: Bool,
        available: Availability
    ) -> [RunnerPlan] {
        guard formats.contains("safetensors") else { return [] }
        var plans: [RunnerPlan] = []
        if checkedOK {
            plans.append(RunnerPlan(runner: .native,
                why: "checked path says compatible — verify with a real hf-load"))
        }
        // MLX-Swift-LM beats the python mlx-lm install as the wide-table
        // alternative: it's our own compiled sibling, no env to break —
        // a partial python env probes fine then dies mid-import.
        if available.mlxSwift {
            plans.append(RunnerPlan(runner: .mlxSwift,
                why: checkedOK
                    ? "posttrainllm-mlxrun — Apple's MLX-Swift-LM impls, the cross-check runner"
                    : "checked path can't run this arch — MLX-Swift-LM's table is wider (MoE, VLM)"))
        }
        if available.mlxLm && isMainRevision {
            plans.append(RunnerPlan(runner: .mlxLm,
                why: checkedOK
                    ? "mlx-lm is the cross-check — widest arch table, auto-downloads to the HF cache"
                    : "checked path can't run this arch, but mlx-lm's table is wider — the installed alternative"))
        }
        return plans
    }

    private static func ggufPlans(
        formats: Set<String>, isMainRevision: Bool, exactGGUF: Bool,
        availability: Availability
    ) -> [RunnerPlan] {
        guard formats.contains("gguf") else { return [] }
        var plans: [RunnerPlan] = []
        if availability.ollama && isMainRevision && !exactGGUF {
            plans.append(RunnerPlan(runner: .ollama,
                why: "GGUF repo + Ollama installed — `ollama run hf.co/` pulls and runs in one step"))
        }
        if availability.lms {
            plans.append(RunnerPlan(runner: .lms,
                why: availability.ollama && isMainRevision && !exactGGUF
                    ? "LM Studio installed — the GGUF fallback if ollama can't pull this repo"
                    : "GGUF repo + LM Studio installed (Ollama absent) — `lms get` then `lms chat`"))
        }
        if availability.llamaCpp && isMainRevision && !exactGGUF {
            plans.append(RunnerPlan(runner: .llamaCpp,
                why: "llama.cpp installed — `llama-cli -hf` pulls and generates directly"))
        }
        return plans
    }

    /// Why nothing can run — the named blocker the CLI prints when
    /// `plans` is empty. Built from the checker's own findings so the
    /// message stays honest about what is missing vs. unsupported.
    public static func blocker(for report: ModelCheckReport,
                               forced: Runner? = nil) -> String {
        if let forced {
            return forcedBlocker(forced, report: report)
        }
        let fmts = Set(report.model.formats)
        var lines = ["no installed runtime can run this repo:"]
        if fmts.contains("gguf") {
            lines.append("  • GGUF weights need Ollama (`brew install ollama`), LM Studio, or llama.cpp — none was detected")
        }
        if fmts.contains("safetensors") {
            if report.checkedPath.status == .expectedToWork
                || report.checkedPath.status == .changesRequired {
                lines.append("  • the checked path cleared but this is unreachable — re-run `model-check`")
            } else {
                lines.append("  • the native loader won't run it: \(report.checkedPath.detail)")
                lines.append("  • mlx-lm covers more architectures — `pip install mlx-lm`, then re-run")
            }
        }
        if fmts.isEmpty {
            lines.append("  • no loadable weight format was identified — see `model-check` for the full report")
        }
        return lines.joined(separator: "\n")
    }

    private static func forcedBlocker(
        _ forced: Runner, report: ModelCheckReport
    ) -> String {
        let exactGGUF = report.model.filePath?.lowercased().hasSuffix(".gguf") == true
        if exactGGUF && (forced == .ollama || forced == .llamaCpp) {
            return "forced --runtime \(forced.rawValue) cannot guarantee the exact GGUF artifact \(report.model.filePath ?? "") — use LM Studio's exact artifact import"
        }
        if report.model.revision != "main",
           [.mlxLm, .ollama, .llamaCpp].contains(forced) {
            return "forced --runtime \(forced.rawValue) cannot guarantee revision \(report.model.revision); use native, mlx-swift, or LM Studio's exact artifact import"
        }
        switch forced {
        case .native:
            if !report.model.formats.contains("safetensors") {
                return "forced --runtime native but \(report.model.id) has no safetensors weights — the native loader reads safetensors, and gguf-load validates rather than generates"
            }
            return "forced --runtime native is unavailable"
        case .mlxSwift:
            return "forced --runtime mlx-swift but posttrainllm-mlxrun is not built — `cd native-mac && swift build --product posttrainllm-mlxrun`"
        case .mlxLm:
            return "forced --runtime mlx-lm but `python3 -m mlx_lm` is not installed (pip install mlx-lm)"
        case .ollama:
            return "forced --runtime ollama but `ollama` is not installed (brew install ollama)"
        case .lms:
            return "forced --runtime lms but the LM Studio CLI (`lms`) is not installed"
        case .llamaCpp:
            return "forced --runtime llama-cli but `llama-cli` is not installed (brew install llama.cpp)"
        }
    }

    private static func installed(_ probes: [ModelCheckReport.RuntimeProbe],
                                  _ name: String) -> Bool {
        probes.contains { $0.name == name && $0.found }
    }
}
