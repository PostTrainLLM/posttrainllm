import SwiftUI

struct WarningBanner: View {
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Theme.warn)
            Text(message)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Theme.fg)
                .fixedSize(horizontal: false, vertical: true)
            Spacer()
        }
        .padding(12)
        .background(Theme.warn.opacity(0.10))
        .overlay(Rectangle().fill(Theme.warn).frame(width: 2), alignment: .leading)
    }
}
