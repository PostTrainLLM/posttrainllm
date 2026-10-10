import SwiftUI
import SaaSMakerUI

/// The native app's instrument palette mirrors browser/src/styles/system.css.
/// SaaSMakerUI owns the semantic roles; teal remains the live-data signal and
/// oxblood remains the brand accent. Start with the closest dark preset.
enum Theme {
    static let palette: SMPalette = {
        let base = Color(red: 10/255, green: 12/255, blue: 15/255)
        var p = SMPalette.baseDark.brand(
            Color(red: 255/255, green: 122/255, blue: 106/255), foreground: base
        )
        p.background = base
        p.surface = Color(red: 17/255, green: 20/255, blue: 25/255)
        p.card = p.surface
        p.secondary = Color(red: 23/255, green: 27/255, blue: 34/255)
        p.border = Color(red: 28/255, green: 33/255, blue: 42/255)
        p.hairline = p.border
        p.input = Color(red: 42/255, green: 48/255, blue: 57/255)
        p.foreground = Color(red: 234/255, green: 237/255, blue: 242/255)
        p.mutedForeground = Color(red: 166/255, green: 173/255, blue: 185/255)
        p.muted = Color(red: 115/255, green: 123/255, blue: 136/255)
        p.accent = Color(red: 72/255, green: 229/255, blue: 194/255)
        p.success = p.accent
        p.primary = p.accent
        p.primaryForeground = base
        p.warning = Color(red: 245/255, green: 177/255, blue: 74/255)
        p.destructive = Color(red: 255/255, green: 104/255, blue: 104/255)
        p.radius = 4
        p.displayWeight = 600
        p.displayTracking = -0.02
        return p
    }()

    static let accent = palette.accent
    static let accentDim = Color(red: 31/255, green: 111/255, blue: 95/255)
    static let accentGlow = palette.accent.opacity(0.20)
    static let brand = palette.brand
    static let brandBright = Color(red: 255/255, green: 145/255, blue: 132/255)
    static let base = palette.background
    static let panel = palette.surface
    static let panel2 = palette.secondary
    static let line = palette.border
    static let lineStrong = palette.input
    static let fg = palette.foreground
    static let muted = palette.mutedForeground
    static let faint = palette.muted
    static let warn = palette.warning
    static let danger = palette.destructive

    static func ui(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .custom(palette.sansFont, size: size).weight(weight)
    }
}

extension Font {
    /// Keep numbers and code monospaced; bundled display type for headings.
    static let tgMono = Font.system(.body, design: .monospaced)
    static let tgDisplay = Font.custom(Theme.palette.displayFont, size: 24).weight(.semibold)
}

extension View {
    /// Shared adapter keeps existing panel content and padding intact.
    func instrumentCard(padding: CGFloat = 0) -> some View {
        SMCard(padding: padding) { self }
    }
}

/// Operational actions use teal (or their warning/danger color), while the
/// root theme keeps oxblood for brand moments. The library owns button layout.
private struct InstrumentAction: ViewModifier {
    let color: Color
    @Environment(\.isEnabled) private var isEnabled

    func body(content: Content) -> some View {
        var p = Theme.palette
        p.primary = color
        return content
            .buttonStyle(SMButtonStyle(.solid))
            .environment(\.smPalette, p)
            .opacity(isEnabled ? 1 : 0.45)
    }
}

extension View {
    func instrumentButton(color: Color = Theme.accent) -> some View {
        modifier(InstrumentAction(color: color))
    }
}
