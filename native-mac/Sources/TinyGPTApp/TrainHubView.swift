import SwiftUI

/// Factory workspace = top-level segmented picker between training modes
/// (pretrain / fine-tune / DPO / distill), each routes to its own view.
/// Restored 2026-06-07 PM after the consolidation pass dropped fine-tune
/// from the sidebar — it was always shipped in the CLI, just hidden in
/// the app.
struct TrainHubView: View {
    enum Mode: String, CaseIterable, Identifiable {
        case pretrain = "Pretrain"
        case finetune = "Fine-tune"
        case dpo      = "DPO"
        case distill  = "Distill"
        var id: String { rawValue }

        var subtitle: String {
            switch self {
            case .pretrain:
                return "Build a baseline model from scratch on a text corpus."
            case .finetune:
                return "SFT / LoRA a base model on target data and save an adapter."
            case .dpo:
                return "Preference tuning from chosen-vs-rejected pairs after SFT data exists."
            case .distill:
                return "Distill a specialist from a larger teacher or stronger local baseline."
            }
        }
    }

    @State private var mode: Mode = .pretrain

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Picker("", selection: $mode) {
                    ForEach(Mode.allCases) { m in Text(m.rawValue).tag(m) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 540)
                Text(mode.subtitle)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
            .background(Theme.panel.opacity(0.5))
            .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)

            Group {
                switch mode {
                case .pretrain: TrainView()
                case .finetune: FinetuneView()
                case .dpo:      DPOView()
                case .distill:  DistillView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(Theme.base)
    }
}
