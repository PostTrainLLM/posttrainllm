import Foundation
import TinyGPTCheck

/// Drives the "Check model compatibility" panel. Calls the same
/// `ModelCheckService` the `posttrainllm model-check` CLI uses — same
/// inspection service, same `ModelCheckReport` schema — on a background
/// queue so the UI stays responsive while Hub metadata is fetched.
///
/// The environment is detected on the user's Mac by default. The manual
/// override fields exist for "will it run on *that* Mac" questions — the
/// report marks environment.source = "manual" so the checked machine is
/// never confused with this one.
@MainActor
final class ModelCheckController: ObservableObject {
    @Published var input: String = ""
    @Published var stage: ModelCheckService.Stage? = nil
    @Published var report: ModelCheckReport? = nil
    @Published var isChecking: Bool = false
    @Published var lastError: String? = nil

    // Manual environment override ("check a different Mac").
    @Published var useManualEnv: Bool = false
    @Published var manualChip: String = ""
    @Published var manualRAMGB: String = ""
    @Published var manualDiskGB: String = ""
    @Published var manualMacOS: String = ""

    func check() {
        let target = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !target.isEmpty, !isChecking else { return }
        isChecking = true
        lastError = nil
        report = nil
        stage = .inspectingRepository

        let env: MacEnvironment? = useManualEnv ? .manual(
            chip: manualChip.isEmpty ? nil : manualChip,
            ramGB: Int(manualRAMGB),
            diskGB: Int(manualDiskGB),
            macOS: manualMacOS.isEmpty ? nil : manualMacOS
        ) : nil

        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let report = try ModelCheckService.check(input: target, environment: env) { s in
                    Task { @MainActor in self.stage = s }
                }
                Task { @MainActor in
                    self.report = report
                    self.isChecking = false
                    self.stage = nil
                }
            } catch {
                Task { @MainActor in
                    self.lastError = "\(error)"
                    self.isChecking = false
                    self.stage = nil
                }
            }
        }
    }
}
