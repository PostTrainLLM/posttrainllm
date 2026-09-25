import SwiftUI

/// Six workspaces. Factory internally has sub-modes
/// (pretrain / fine-tune / DPO / distill). The current product center is the
/// factory loop: target -> data -> post-training -> eval -> package -> report.
enum AppTab: Hashable {
    case gallery     // every loadable model + chat with whichever is loaded
    case train       // factory/post-training workspace (sub-modes)
    case runs        // orchestration: factory-run validate/publish-check, SQL eval, generate
    case eval        // score + compare
    case trace       // inference heatmap
    case interp      // mech-interp power tools
    case serve       // HTTP endpoint
    case check       // HF model compatibility check (issue #156)
    // Removed 2026-06-17:
    //  - .sample  → renamed to .gallery (was previously two distinct tabs
    //              which duplicated each other; one workspace owns picker +
    //              chat now, see mainPane)
    //  - .roadmap → docs/PLAN.md is canonical; no product surface needed
    //  - .learn   → docs are reachable via Finder + repo browser, the in-app
    //              markdown viewer was duplicative
}

struct ContentView: View {
    @StateObject private var controller = ModelController()
    @StateObject private var controllerB = ModelController(historyKey: "tg.completionHistory.compare.v1")
    @State private var compareMode: Bool = false
    @State private var inspectorBeforeCompare: Bool = true
    @StateObject private var stats = MachineStats()
    @StateObject private var hfBrowser = HFBrowserController()
    @State private var galleryItems: [GalleryItem] = []
    @State private var selectedItem: GalleryItem? = nil
    @State private var showModelLibrary: Bool = true
    @State private var showClearHistoryConfirmation: Bool = false
    @State private var showHFBrowser: Bool = false
    @AppStorage("posttrainllm.gallery.expanded") private var galleryExpanded: Bool = false

    // Sampler params — persisted across launches so a tuned recipe sticks.
    @AppStorage("tg.prompt")        private var prompt: String = "ROMEO:"
    @AppStorage("tg.maxTokens")     private var maxTokens: Int = 200
    @AppStorage("tg.temperature")   private var temperature: Double = 0.8
    @AppStorage("tg.topK")          private var topK: Int = 0
    @AppStorage("tg.repPenalty")    private var repPenalty: Double = 1.0
    @AppStorage("tg.showInspector") private var showInspector: Bool = true

    @State private var tab: AppTab = .gallery
    @State private var liveServes: [ServeProcess] = []
    // Sidebar nav default lands on Gallery — most common "use a model" entry.

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                sidebar
                    .frame(width: 84)
                    .background(Theme.panel)

                Divider().background(Theme.line)

                VStack(spacing: 0) {
                    Group {
                        switch tab {
                        case .gallery:    mainPane
                        case .train:      TrainHubView()
                        case .runs:       RunsHubView()
                        case .eval:       EvalView()
                        case .trace:      InferenceHeatmapView()
                        case .interp:     InterpView()
                        case .serve:      ServerView()
                        case .check:      ModelCheckView()
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .background(Theme.base)
            }

            // Machine-stats strip — sticky bottom, mono+compact
            Divider().background(Theme.line)
            machineStatsBar
        }
        .onAppear {
            galleryItems = GalleryDiscovery.discover()
            liveServes = ServeRegistry.discover()
        }
        .onReceive(Timer.publish(every: 5, on: .main, in: .common).autoconnect()) { _ in
            liveServes = ServeRegistry.discover()
        }
        .sheet(isPresented: $showHFBrowser) {
            HFBrowserView(controller: hfBrowser, isPresented: $showHFBrowser)
        }
        .confirmationDialog("Clear this model's run history?",
                            isPresented: $showClearHistoryConfirmation,
                            titleVisibility: .visible) {
            Button("Clear history", role: .destructive) { controller.clearHistory() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Completed runs for this model will be removed from this Mac.")
        }
    }

    private var machineStatsBar: some View {
        HStack(spacing: 14) {
            Image(systemName: "circle.fill")
                .font(.system(size: 6))
                .foregroundStyle(Theme.accent)
                .accessibilityHidden(true)
            statsBlock("LOCAL", stats.cpuModel.replacingOccurrences(of: "Apple ", with: ""))
            Text(controller.status)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.muted)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: .infinity, alignment: .leading)
            statsBlock("APP RAM", FormatBytes.compact(stats.processRSSBytes))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 9)
        .background(Theme.panel2)
    }

    private func statsBlock(_ label: String, _ value: String) -> some View {
        HStack(spacing: 4) {
            Text(label)
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.faint)
                .tracking(1)
            Text(value)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.fg)
        }
    }

    // Old top tabBar + grouped sections — replaced 2026-06-07 PM
    // after user audit consolidated to 6 flat workspaces.

    /// Compact workspace rail. Labels remain visible, and each whole tile is
    /// a keyboard-reachable target with a full descriptive accessibility name.
    private func navRow(_ which: AppTab, icon: String, label: String) -> some View {
        let active = tab == which
        return Button {
            tab = which
            if which == .gallery { showModelLibrary = true }
        } label: {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(active ? Theme.accent : Theme.muted)
                Text(label)
                    .font(.system(size: 10, weight: active ? .semibold : .medium))
                    .foregroundStyle(active ? Theme.fg : Theme.muted)
            }
            .frame(width: 64, height: 44)
            .contentShape(Rectangle())
            .background(active ? Theme.accent.opacity(0.13) : Color.clear,
                        in: RoundedRectangle(cornerRadius: 10))
            .overlay(alignment: .topTrailing) {
                if which == .serve && !liveServes.isEmpty {
                    Circle().fill(Theme.accent).frame(width: 6, height: 6)
                        .padding(7)
                }
            }
        }
        .buttonStyle(.plain)
        .help(label)
        .accessibilityLabel(label)
        .accessibilityAddTraits(active ? .isSelected : [])
    }

    private func tabButton(_ which: AppTab, label: String) -> some View {
        let active = tab == which
        return Button {
            tab = which
        } label: {
            VStack(spacing: 6) {
                Text(label)
                    .font(.system(size: 13, weight: active ? .semibold : .regular))
                    .foregroundStyle(active ? Theme.accent : Theme.muted)
                Rectangle()
                    .fill(active ? Theme.accent : Color.clear)
                    .frame(height: 2)
            }
            .padding(.horizontal, 12)
        }
        .buttonStyle(.plain)
    }

    private var sidebar: some View {
        VStack(spacing: 0) {
            Text("P")
                .font(.system(size: 27, weight: .bold, design: .rounded))
                .foregroundStyle(Theme.accent)
                .frame(width: 64, height: 56)
                .help("posttrainllm · Mac factory")
                .accessibilityLabel("posttrainllm Mac factory")

            ScrollView(showsIndicators: true) {
                VStack(spacing: 2) {
                    navRow(.gallery,    icon: "rectangle.grid.2x2",                label: "Gallery")
                    navRow(.train,      icon: "waveform.path.ecg",                 label: "Factory")
                    navRow(.runs,       icon: "shippingbox",                       label: "Runs")
                    navRow(.eval,       icon: "checkmark.gobackward",              label: "Eval")
                    navRow(.trace,      icon: "chart.bar.xaxis",                   label: "Trace")
                    navRow(.interp,     icon: "scope",                             label: "Interp")
                    navRow(.serve,      icon: "antenna.radiowaves.left.and.right", label: "Serve")
                    navRow(.check,      icon: "checkmark.shield",                  label: "Check")
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 8)
            }

            Divider().background(Theme.line)
            VStack(spacing: 3) {
                Button { showHFBrowser = true } label: {
                    Image(systemName: "cloud.fill")
                        .font(.system(size: 15))
                        .frame(width: 48, height: 28)
                }
                .help("Browse and download Hugging Face models")
                .accessibilityLabel("Browse Hugging Face models")
                Button { openModelFile() } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 17, weight: .medium))
                        .frame(width: 48, height: 28)
                }
                .help("Open a model file")
                .accessibilityLabel("Open a model file")
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.muted)
            .padding(.vertical, 6)
        }
    }

    /// Gallery workspace — a grid of model cards. Each card has 3
    /// actions: Chat (Sample), Eval, Interp. Replaces the old
    /// collapsible-in-sidebar approach which buried the models.
    private var galleryPane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Gallery")
                        .font(.tgDisplay)
                        .foregroundStyle(Theme.fg)
                    Text("models loadable from data/gallery/ + ~/.cache/posttrainllm/runs/ · click an action below each model")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(Theme.muted)
                }
                if galleryItems.isEmpty {
                    Text("no models found. drop .tinygpt files into data/gallery/ or train via Train tab.")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                } else {
                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: 16),
                        GridItem(.flexible(), spacing: 16),
                    ], spacing: 16) {
                        ForEach(galleryItems) { item in
                            galleryCardWithActions(item)
                        }
                    }
                }
            }
            .padding(.horizontal, 32)
            .padding(.vertical, 28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.base)
    }

    /// The first action starts a local run; Eval and Interp remain direct paths.
    private func galleryCardWithActions(_ item: GalleryItem) -> some View {
        let fileSize = (try? item.url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        return VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                Text(item.icon).font(.system(size: 30))
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.displayName)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(Theme.fg)
                        .lineLimit(1)
                    Text("\(item.url.lastPathComponent)  ·  \(FormatBytes.compact(fileSize))")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer(minLength: 0)
            }
            Text("STARTING PROMPT   " + item.prompt.trimmingCharacters(in: .whitespacesAndNewlines))
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.muted)
                .lineLimit(1)
            Divider().background(Theme.line)
            HStack(spacing: 8) {
                galleryActionButton(label: "Generate", icon: "arrow.up.right", prominent: true) {
                    selectedItem = item
                    prompt = item.prompt
                    if controller.loadedItem?.id != item.id {
                        Task { await controller.load(item) }
                    }
                    showModelLibrary = false
                    tab = .gallery
                }
                galleryActionButton(label: "Eval", icon: "checkmark.gobackward") {
                    selectedItem = item
                    // Pin model path into UserDefaults so EvalController's
                    // init picks it up — EvalView is created fresh on tab
                    // switch and its controller has no other way to see
                    // the gallery's selection.
                    UserDefaults.standard.set(item.url.path, forKey: "tg.eval.modelPath")
                    Task { await controller.load(item) }
                    tab = .eval
                }
                galleryActionButton(label: "Interp", icon: "scope") {
                    selectedItem = item
                    // Same — InterpView reads tg.interp.modelPath via
                    // @AppStorage so this lands before the view appears.
                    UserDefaults.standard.set(item.url.path, forKey: "tg.interp.modelPath")
                    Task { await controller.load(item) }
                    tab = .interp
                }
            }
        }
        .padding(20)
        .background(Theme.panel, in: RoundedRectangle(cornerRadius: 13))
        .overlay(RoundedRectangle(cornerRadius: 13).stroke(Theme.lineStrong))
    }

    private func galleryActionButton(label: String, icon: String,
                                     prominent: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 10))
                Text(label)
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
            }
            .foregroundStyle(prominent ? Theme.base : Theme.accent)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(prominent ? Theme.accent : Theme.accent.opacity(0.12),
                        in: RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
    }

    /// Inline grid-card for the Sample placeholder. Click loads the model
    /// + jumps to the generation pane.
    private func modelCard(_ item: GalleryItem) -> some View {
        Button {
            selectedItem = item
            prompt = item.prompt
            Task { await controller.load(item) }
        } label: {
            HStack(spacing: 12) {
                Text(item.icon)
                    .font(.system(size: 24))
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.displayName)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(Theme.fg)
                        .lineLimit(1)
                    Text(item.url.deletingLastPathComponent().lastPathComponent + "/")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
            .background(Theme.panel)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    /// Collapsible gallery row — single line when collapsed; click to expand.
    private var gallerySidebarSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                galleryExpanded.toggle()
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: galleryExpanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Theme.faint)
                        .frame(width: 12)
                    Text("Gallery")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(Theme.muted)
                    Spacer(minLength: 0)
                    Text("\(galleryItems.count)")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.panel2)
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity, minHeight: 32, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if galleryExpanded {
                if galleryItems.isEmpty {
                    Text("no models in data/gallery/")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                        .padding(.horizontal, 32)
                        .padding(.bottom, 6)
                } else {
                    ForEach(galleryItems) { item in
                        galleryRow(item)
                            .padding(.leading, 12)
                    }
                }
            }
        }
        .padding(.top, 8)
    }

    private func galleryRow(_ item: GalleryItem) -> some View {
        let isSelected = controller.loadedItem?.id == item.id
        return Button {
            selectedItem = item
            prompt = item.prompt
            Task { await controller.load(item) }
        } label: {
            HStack(spacing: 10) {
                Text(item.icon)
                    .font(.system(size: 18))
                Text(item.displayName)
                    .font(.system(size: 13, weight: isSelected ? .medium : .regular))
                    .foregroundStyle(isSelected ? Theme.accent : Theme.fg)
                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(minHeight: 32)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(isSelected ? Theme.accentGlow : Color.clear)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var mainPane: some View {
        if showModelLibrary || controller.loadedItem == nil {
            placeholderPane
        } else {
            generationPane
        }
    }

    private var placeholderPane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 25) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("LOCAL MODEL LIBRARY")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .tracking(1)
                        .foregroundStyle(Theme.accent)
                    Text("Pick a model. Start a run.")
                        .font(.system(size: 27, weight: .semibold))
                        .foregroundStyle(Theme.fg)
                    Text("Generate, evaluate, or inspect the checkpoints available on this Mac.")
                        .font(.system(size: 14))
                        .foregroundStyle(Theme.muted)
                    if controller.status.contains("failed") {
                        Text(controller.status)
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.danger)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if let loaded = controller.loadedItem {
                        Button {
                            showModelLibrary = false
                        } label: {
                            Label("Continue \(loaded.displayName) run", systemImage: "arrow.right")
                        }
                        .buttonStyle(.plain)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Theme.accent)
                        .padding(.top, 8)
                    }
                }

                if galleryItems.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "tray")
                            .font(.system(size: 28))
                            .foregroundStyle(Theme.faint)
                        Text("No models found")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(Theme.muted)
                        Text("Open a checkpoint with +, browse Hugging Face with the cloud button, or train one in Factory.")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(Theme.faint)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity, minHeight: 240)
                } else {
                    // Show all models with direct Generate / Eval / Interp
                    // actions so the workspace doubles as a hub: jump straight to
                    // any surface from any model.
                    HStack {
                        Text("AVAILABLE MODELS")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .tracking(1)
                            .foregroundStyle(Theme.faint)
                        Spacer()
                        Text("\(galleryItems.count) LOCAL")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .foregroundStyle(Theme.muted)
                    }
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 330), spacing: 16)],
                              alignment: .leading, spacing: 16) {
                        ForEach(galleryItems) { item in
                            galleryCardWithActions(item)
                        }
                    }
                }
            }
            .frame(maxWidth: 1120, alignment: .leading)
            .padding(.horizontal, 32)
            .padding(.vertical, 44)
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .background(Theme.base)
    }

    /// Keep the in-progress stream and completed history mutually exclusive.
    /// The old layout showed the latest completion twice after a run.
    private func outputColumn(controller: ModelController, label: String) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if compareMode {
                    HStack(spacing: 6) {
                        Text(label).foregroundStyle(Theme.accent)
                        Text(controller.loadedItem?.displayName ?? "Pick a model")
                            .foregroundStyle(Theme.muted)
                        Spacer()
                    }
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                }

                if controller.isGenerating {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("GENERATING · LIVE OUTPUT")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .tracking(1)
                            .foregroundStyle(Theme.accent)
                        Text(controller.generated)
                            .font(.tgMono)
                            .foregroundStyle(Theme.fg)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(24)
                    .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
                    .background(Theme.panel, in: RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.lineStrong))
                } else if let latest = controller.historyForCurrentModel.last {
                    historyCard(latest, heading: "LATEST RUN")
                } else {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("READY FOR A RUN")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .tracking(1)
                            .foregroundStyle(Theme.accent)
                        Text("Enter a prompt below to generate with this local model.")
                            .font(.system(size: 15))
                            .foregroundStyle(Theme.muted)
                    }
                    .padding(24)
                    .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
                    .background(Theme.panel, in: RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.lineStrong))
                }

                let earlierRuns = controller.isGenerating
                    ? controller.historyForCurrentModel
                    : Array(controller.historyForCurrentModel.dropLast())
                if !earlierRuns.isEmpty {
                    Text(controller.isGenerating ? "PREVIOUS RUNS" : "EARLIER RUNS")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .tracking(1)
                        .foregroundStyle(Theme.faint)
                        .padding(.top, 10)
                    ForEach(Array(earlierRuns.reversed())) { item in
                        historyCard(item, heading: "RUN")
                    }
                }
            }
            .frame(maxWidth: 900, alignment: .leading)
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .background(Theme.base)
    }

    private func historyCard(_ item: ModelController.HistoryItem, heading: String) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(heading).foregroundStyle(Theme.accent)
                Spacer()
                Text(item.timestamp, format: .dateTime.hour().minute().second())
                    .foregroundStyle(Theme.faint)
            }
            .font(.system(size: 10, weight: .semibold, design: .monospaced))
            .tracking(1)
            Divider().background(Theme.line)
            VStack(alignment: .leading, spacing: 8) {
                Text("PROMPT")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.faint)
                    .tracking(1)
                Text(item.prompt)
                    .font(.system(size: 16, design: .monospaced))
                    .foregroundStyle(Theme.fg)
                    .textSelection(.enabled)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("COMPLETION")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.faint)
                    .tracking(1)
                Text(item.output)
                    .font(.system(size: 20, design: .monospaced))
                    .foregroundStyle(Theme.fg)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            Divider().background(Theme.line)
            HStack(spacing: 12) {
                Text("T=\(String(format: "%.2f", item.temperature))")
                if item.topK > 0 { Text("top-k=\(item.topK)") }
                if item.repetitionPenalty > 1.001 { Text("rp=\(String(format: "%.2f", item.repetitionPenalty))") }
                Text("\(item.tokensGenerated) tok")
                Text(String(format: "%.0f tok/s", item.tokensPerSec))
                Spacer(minLength: 0)
                Button {
                    let pb = NSPasteboard.general
                    pb.clearContents()
                    pb.setString(item.output, forType: .string)
                } label: { Text("Copy") }
                .buttonStyle(.plain)
                .foregroundStyle(Theme.accent)
                .accessibilityLabel("Copy generated text")
            }
            .font(.system(size: 10, design: .monospaced))
            .foregroundStyle(Theme.muted)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.panel, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.lineStrong))
    }

    private func welcomeRow(icon: String, title: String, description: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(Theme.accent)
                .frame(width: 24, height: 24, alignment: .center)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.fg)
                Text(description)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
    }

    private var generationPane: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .center, spacing: 16) {
                    VStack(alignment: .leading, spacing: 5) {
                        Button {
                            showModelLibrary = true
                        } label: {
                            Text("GALLERY  /  \(controller.loadedItem?.displayName.uppercased() ?? "MODEL")")
                        }
                        .buttonStyle(.plain)
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .tracking(1)
                            .foregroundStyle(Theme.accent)
                        Text("Run a local model")
                            .font(.system(size: 24, weight: .semibold))
                            .foregroundStyle(Theme.fg)
                    }
                    Spacer(minLength: 8)
                    Button {
                        compareMode.toggle()
                        if compareMode {
                            inspectorBeforeCompare = showInspector
                            showInspector = false
                        } else {
                            controllerB.cancelGeneration()
                            showInspector = inspectorBeforeCompare
                        }
                    } label: {
                        Label(compareMode ? "Comparing" : "Compare", systemImage: "rectangle.split.2x1")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(compareMode ? Theme.accent : Theme.muted)
                    .help("Run a second model side-by-side on the same prompt")
                    Button {
                        showInspector.toggle()
                    } label: {
                        Label("Settings", systemImage: "slider.horizontal.3")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(showInspector ? Theme.accent : Theme.muted)
                    .help(showInspector ? "Hide sampling settings" : "Show sampling settings")
                }

                HStack(spacing: 14) {
                    Text(controller.loadedItem?.icon ?? "•")
                        .font(.system(size: 25))
                    VStack(alignment: .leading, spacing: 4) {
                        Text(controller.loadedItem?.displayName ?? "")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(Theme.fg)
                        Text("\(formattedInt(controller.paramCount)) parameters  ·  \(controller.deviceName)")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(Theme.muted)
                    }
                    Spacer(minLength: 0)
                    Text(controller.isGenerating ? "GENERATING" : "MODEL READY")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.accent)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(Theme.accent.opacity(0.12),
                                    in: RoundedRectangle(cornerRadius: 7))
                }
                .padding(15)
                .background(Theme.panel2, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lineStrong))
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 18)
            Divider().background(Theme.line)

            // Compare mode: second model picker (model B). Renders as a
            // pill strip above the output panes — visible only in compare
            // mode so the single-model view stays minimal.
            if compareMode {
                HStack(spacing: 12) {
                    Text("B:")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                    if let b = controllerB.loadedItem {
                        Text(b.icon + " " + b.displayName)
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(Theme.fg)
                    } else {
                        Text("pick a second model")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(Theme.faint)
                    }
                    Spacer()
                    Menu("change") {
                        ForEach(galleryItems) { item in
                            Button(item.displayName) {
                                Task { await controllerB.load(item) }
                            }
                        }
                    }
                    .menuStyle(.borderlessButton)
                    .frame(width: 90)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 8)
                .background(Theme.panel.opacity(0.5))
                .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)
            }

            // Output + inspector. Compare mode splits the output area
            // into two columns (A | B) that both run on the same prompt.
            HStack(spacing: 0) {
                outputColumn(controller: controller, label: "A")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                if compareMode {
                    Divider().background(Theme.line)
                    outputColumn(controller: controllerB, label: "B")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }

                if showInspector {
                    Divider().background(Theme.line)
                    samplerInspector
                        .frame(width: 250)
                        .frame(maxHeight: .infinity)
                        .background(Theme.panel)
                }
            }

            Divider().background(Theme.line)

            // Keep the prompt and primary action anchored in the viewport.
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("NEW PROMPT")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .tracking(1)
                        .foregroundStyle(Theme.accent)
                    Spacer()
                    Text("⌘↵ to generate")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                }
                HStack(spacing: 12) {
                    TextField("Prompt", text: $prompt, axis: .horizontal)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 14)
                        .frame(minHeight: 42)
                        .background(Theme.base, in: RoundedRectangle(cornerRadius: 9))
                        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.lineStrong))
                        .font(.tgMono)
                        .accessibilityLabel("Prompt")

                    if controller.isGenerating || (compareMode && controllerB.isGenerating) {
                        Button("Stop") {
                            controller.cancelGeneration()
                            if compareMode { controllerB.cancelGeneration() }
                        }
                        .keyboardShortcut(.cancelAction)
                        .buttonStyle(PrimaryButtonStyle(color: Theme.danger))
                    } else {
                        Button("Generate") {
                            controller.generate(prompt: prompt, maxTokens: maxTokens,
                                                temperature: Float(temperature),
                                                topK: topK,
                                                repetitionPenalty: Float(repPenalty))
                            if compareMode && controllerB.loadedItem != nil {
                                controllerB.generate(prompt: prompt, maxTokens: maxTokens,
                                                     temperature: Float(temperature),
                                                     topK: topK,
                                                     repetitionPenalty: Float(repPenalty))
                            }
                        }
                        .keyboardShortcut(.return, modifiers: [.command])
                        .buttonStyle(PrimaryButtonStyle(color: Theme.accent))
                        .disabled(controller.loadedItem == nil ||
                                  (compareMode && controllerB.loadedItem == nil))
                    }
                }
                HStack(spacing: 16) {
                    Button(controller.isEvaluating ? "Scoring…" : "Score a text file") {
                        runEval()
                    }
                    .buttonStyle(.plain)
                    .disabled(controller.loadedItem == nil || controller.isEvaluating)
                    .help("Score a UTF-8 text file with cross-entropy, BPB, and perplexity")
                    if !controller.historyForCurrentModel.isEmpty {
                        Button("Clear history") { showClearHistoryConfirmation = true }
                            .buttonStyle(.plain)
                            .help("Clear completion history for the current model only")
                    }
                    Spacer()
                    Text("\(maxTokens) max tokens")
                        .foregroundStyle(Theme.faint)
                }
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.muted)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 17)
            .background(Theme.panel2)

            if let result = controller.evalResult {
                HStack {
                    Text("EVAL")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.accent)
                        .tracking(1)
                    Text(result)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Theme.fg)
                    Spacer()
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 8)
                .background(Theme.accentGlow)
            }
        }
    }

    // MARK: - Sampler inspector

    /// Right-hand inspector panel. Mirrors what LM Studio/Ollama users
    /// expect from a "decent" local-AI app: temperature, top-K,
    /// repetition penalty, max tokens. Persisted via @AppStorage so the
    /// tuned recipe survives a restart.
    private var samplerInspector: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("SAMPLING")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.faint)
                    .tracking(1)
                    .padding(.top, 18)

                inspectorRow(
                    label: "Temperature",
                    hint: "0 = greedy · 1 = sample raw · >1 = more random",
                    value: temperature,
                    range: 0...2,
                    format: "%.2f"
                ) { temperature = $0 }

                inspectorRow(
                    label: "Top-K",
                    hint: topK == 0 ? "0 = off — sample over full vocab" :
                                       "keep only the \(topK) highest-prob tokens",
                    value: Double(topK),
                    range: 0...256,
                    format: "%.0f"
                ) { topK = Int($0) }

                inspectorRow(
                    label: "Rep. penalty",
                    hint: repPenalty <= 1.001 ? "1.0 = off — Keskar et al. 2019" :
                                                 "divides logits of recent tokens",
                    value: repPenalty,
                    range: 1.0...2.0,
                    format: "%.2f"
                ) { repPenalty = $0 }

                Divider().background(Theme.line).padding(.vertical, 4)

                Text("LENGTH")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.faint)
                    .tracking(1)

                HStack {
                    Text("max tokens")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Theme.muted)
                    Spacer()
                    TextField("", value: $maxTokens, format: .number)
                        .accessibilityLabel("Maximum tokens")
                        .textFieldStyle(.plain)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(Theme.panel2)
                        .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.line))
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                        .font(.system(size: 12, design: .monospaced))
                }

                Spacer(minLength: 16)

                Button {
                    temperature = 0.8
                    topK = 0
                    repPenalty = 1.0
                    maxTokens = 200
                } label: {
                    HStack {
                        Image(systemName: "arrow.counterclockwise")
                        Text("Reset to defaults")
                    }
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.muted)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 20)
        }
    }

    /// One labeled slider row with current value + hint text. Generic over
    /// the slider type so int / float fields share one layout.
    private func inspectorRow(label: String, hint: String, value: Double,
                              range: ClosedRange<Double>, format: String,
                              setter: @escaping (Double) -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(Theme.fg)
                Spacer()
                Text(String(format: format, value))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.muted)
            }
            Slider(
                value: Binding(get: { value }, set: setter),
                in: range
            )
            .accessibilityLabel(label)
            .accessibilityValue(String(format: format, value))
            .controlSize(.small)
            .tint(Theme.accent)
            Text(hint)
                .font(.system(size: 10))
                .foregroundStyle(Theme.faint)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func runEval() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.plainText, .utf8PlainText, .text]
        panel.allowsMultipleSelection = false
        panel.message = "Pick a UTF-8 text file to score the model on."
        if panel.runModal() == .OK, let url = panel.url {
            do {
                let data = try Data(contentsOf: url)
                controller.evaluate(corpus: data)
            } catch {
                controller.evalResult = "couldn't read \(url.lastPathComponent): \(error)"
            }
        }
    }

    /// File-picker entry to the sidebar "+" button. Any .tinygpt file
    /// becomes a one-off GalleryItem with the filename as display name.
    /// The item isn't added to the persistent gallery list — close +
    /// reopen the app to re-pick — but it loads + samples identically
    /// to a gallery entry.
    private func openModelFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        // Allow any extension type — .tinygpt is custom, .bin is the
        // browser-shipping format, and macOS would otherwise hide both.
        panel.allowedContentTypes = [.data]
        panel.message = "Pick a .tinygpt or .bin model checkpoint."
        if panel.runModal() == .OK, let url = panel.url {
            let stem = url.deletingPathExtension().lastPathComponent
            let item = GalleryItem(
                id: "user-\(stem)-\(UUID().uuidString.prefix(6))",
                displayName: stem.replacingOccurrences(of: "-", with: " ").capitalized,
                icon: "📦",
                url: url,
                prompt: "Hello"
            )
            // Append to the sidebar list so it's selectable for this session.
            if !galleryItems.contains(where: { $0.url == item.url }) {
                galleryItems.append(item)
            }
            selectedItem = item
            showModelLibrary = false
            tab = .gallery
            Task { await controller.load(item) }
        }
    }

    private func formattedInt(_ n: Int) -> String {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        return f.string(from: NSNumber(value: n)) ?? "\(n)"
    }
}

private struct PrimaryButtonStyle: ButtonStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(color.opacity(configuration.isPressed ? 0.25 : 0.15))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(color.opacity(0.5), lineWidth: 1)
            )
    }
}
