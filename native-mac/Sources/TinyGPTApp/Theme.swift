import SwiftUI

/// The native app is the "instrument" mode of the one posttrainllm design
/// system. These values mirror the `[data-theme="instrument"]` scope of
/// `browser/src/styles/system.css` exactly, so the Mac app and the website read
/// as one product: teal is the shared "live data" signal across both surfaces;
/// oxblood (`brand`) is the shared brand accent.
enum Theme {
    /// Teal — the shared "this is alive" signal (web `--live` in instrument
    /// mode). Loss curve, active controls, the GPU-active dot.
    static let accent = Color(red: 72/255, green: 229/255, blue: 194/255)   // #48e5c2
    static let accentDim = Color(red: 31/255, green: 111/255, blue: 95/255)
    static let accentGlow = Color(red: 72/255, green: 229/255, blue: 194/255, opacity: 0.20)

    /// Oxblood — the shared brand accent (web `--brand`, brightened for dark).
    static let brand = Color(red: 255/255, green: 122/255, blue: 106/255)    // #ff7a6a
    static let brandBright = Color(red: 255/255, green: 145/255, blue: 132/255)

    /// Surface colors — three depths matching the browser's `--base`, `--panel`,
    /// `--panel-2`.
    static let base = Color(red: 8/255, green: 9/255, blue: 10/255)
    static let panel = Color(red: 13/255, green: 14/255, blue: 16/255)
    static let panel2 = Color(red: 20/255, green: 21/255, blue: 24/255)
    static let line = Color(red: 29/255, green: 31/255, blue: 35/255)
    static let lineStrong = Color(red: 44/255, green: 47/255, blue: 53/255)

    /// Foreground hierarchy.
    static let fg = Color(red: 231/255, green: 232/255, blue: 234/255)
    static let muted = Color(red: 146/255, green: 150/255, blue: 160/255)
    static let faint = Color(red: 120/255, green: 125/255, blue: 136/255)

    static let warn = Color(red: 245/255, green: 177/255, blue: 74/255)
    static let danger = Color(red: 255/255, green: 104/255, blue: 104/255)
}

extension Font {
    /// Tight monospace for numbers + code samples.
    static let tgMono = Font.system(.body, design: .monospaced)
    /// Display heading.
    static let tgDisplay = Font.system(size: 24, weight: .semibold)
}
