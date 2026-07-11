import Foundation

/// Human-readable byte size (binary units: KiB/MiB/GiB, labelled KB/MB/GB).
///
/// One shared formatter for every CLI/UI surface — replaced ~15 near-identical
/// private copies that had drifted between binary and decimal units.
public func formatBytes(_ n: Int) -> String {
    if n >= 1 << 30 { return String(format: "%.2f GB", Double(n) / Double(1 << 30)) }
    if n >= 1 << 20 { return String(format: "%.1f MB", Double(n) / Double(1 << 20)) }
    if n >= 1 << 10 { return String(format: "%.1f KB", Double(n) / Double(1 << 10)) }
    return "\(n) B"
}

/// Integer with thousands separators (e.g. 1234567 -> "1,234,567").
/// Shared replacement for the identical private copies across CLI/UI surfaces.
public func formatNum(_ n: Int) -> String {
    let f = NumberFormatter(); f.numberStyle = .decimal
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}
