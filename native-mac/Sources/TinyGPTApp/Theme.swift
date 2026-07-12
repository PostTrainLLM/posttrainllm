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

    /// Surface colors — exactly the web system's `--paper`, `--paper-raised`,
    /// `--paper-2`, `--rule`, `--rule-2` (browser/src/styles/system.css), so
    /// the app and the site are literally one palette.
    static let base = Color(red: 10/255, green: 12/255, blue: 15/255)        // #0a0c0f
    static let panel = Color(red: 17/255, green: 20/255, blue: 25/255)       // #111419
    static let panel2 = Color(red: 23/255, green: 27/255, blue: 34/255)      // #171b22
    static let line = Color(red: 28/255, green: 33/255, blue: 42/255)        // #1c212a
    static let lineStrong = Color(red: 42/255, green: 48/255, blue: 57/255)  // #2a3039

    /// Foreground hierarchy — web `--ink`, `--ink-70`, `--ink-55`.
    static let fg = Color(red: 234/255, green: 237/255, blue: 242/255)       // #eaedf2
    static let muted = Color(red: 166/255, green: 173/255, blue: 185/255)    // #a6adb9
    static let faint = Color(red: 115/255, green: 123/255, blue: 136/255)    // #737b88

    static let warn = Color(red: 245/255, green: 177/255, blue: 74/255)
    static let danger = Color(red: 255/255, green: 104/255, blue: 104/255)
}

extension Font {
    /// Tight monospace for numbers + code samples.
    static let tgMono = Font.system(.body, design: .monospaced)
    /// Display heading.
    static let tgDisplay = Font.system(size: 24, weight: .semibold)
}
