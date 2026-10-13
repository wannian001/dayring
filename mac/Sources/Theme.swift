import AppKit
import SwiftUI

extension NSColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(srgbRed: CGFloat((hex >> 16) & 0xff) / 255, green: CGFloat((hex >> 8) & 0xff) / 255,
                  blue: CGFloat(hex & 0xff) / 255, alpha: alpha)
    }
}

/// Colours from healthaio/web/css/tokens.css: graphite neutrals and a blue accent in light mode, dusk neutrals and
/// a violet accent in dark mode. Data colours keep their hue in both (focus blue, fun orange, comms aqua, sleep
/// violet); good / watch / off are only used next to a word.
enum Palette {
    static func pair(_ light: NSColor, _ dark: NSColor) -> NSColor {
        NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? dark : light
        }
    }

    static func hex(_ light: UInt32, _ dark: UInt32) -> NSColor { pair(NSColor(hex: light), NSColor(hex: dark)) }

    static let bg = hex(0xf4f4f3, 0x0b0d13)
    static let surface = hex(0xffffff, 0x141822)
    static let surface2 = hex(0xf7f7f6, 0x1a1f2b)
    static let ink = hex(0x161616, 0xeceef5)
    static let ink2 = hex(0x4a4a48, 0xb4bbcc)
    static let ink3 = hex(0x6a6a67, 0x8c95a8)
    static let line = hex(0xe4e4e1, 0x232937)
    static let line2 = hex(0xcfcfcb, 0x313849)
    static let band = pair(NSColor(hex: 0x161616, alpha: 0.075), NSColor(hex: 0xeceef5, alpha: 0.085))

    static let accent = hex(0x1f5fbf, 0xaea2f7)
    static let accentSoft = pair(NSColor(hex: 0x1f5fbf, alpha: 0.1), NSColor(hex: 0xaea2f7, alpha: 0.14))
    static let onAccent = hex(0xffffff, 0x14102e)

    static let focus = hex(0x2a78d6, 0x3987e5)
    static let fun = hex(0xeb6834, 0xd95926)
    static let comms = hex(0x1baf7a, 0x199e70)
    static let sleep = hex(0x4a3aa7, 0x9085e9)

    static let good = NSColor(hex: 0x0ca30c)
    static let watch = NSColor(hex: 0xfab219)
    static let off = NSColor(hex: 0xd03b3b)
    static let goodInk = hex(0x1d7a1d, 0x4cc94c)
    static let watchInk = hex(0x8a5a00, 0xf5bd4a)
    static let offInk = hex(0xb42828, 0xf27c7c)
    static let watchSoft = pair(NSColor(hex: 0xfab219, alpha: 0.16), NSColor(hex: 0xfab219, alpha: 0.14))
}

/// The same colours for SwiftUI.
enum Tok {
    static var bg: Color { Color(nsColor: Palette.bg) }
    static var surface: Color { Color(nsColor: Palette.surface) }
    static var surface2: Color { Color(nsColor: Palette.surface2) }
    static var ink: Color { Color(nsColor: Palette.ink) }
    static var ink2: Color { Color(nsColor: Palette.ink2) }
    static var ink3: Color { Color(nsColor: Palette.ink3) }
    static var line: Color { Color(nsColor: Palette.line) }
    static var line2: Color { Color(nsColor: Palette.line2) }
    static var band: Color { Color(nsColor: Palette.band) }
    static var accent: Color { Color(nsColor: Palette.accent) }
    static var accentSoft: Color { Color(nsColor: Palette.accentSoft) }
    static var onAccent: Color { Color(nsColor: Palette.onAccent) }
    static var focus: Color { Color(nsColor: Palette.focus) }
    static var fun: Color { Color(nsColor: Palette.fun) }
    static var comms: Color { Color(nsColor: Palette.comms) }
    static var sleep: Color { Color(nsColor: Palette.sleep) }
    static var watchSoft: Color { Color(nsColor: Palette.watchSoft) }
}

/// good / watch / off, plus "nothing to say" and "working on it".
enum Tone {
    case good, watch, off, neutral, busy

    var fill: Color {
        switch self {
        case .good: return Color(nsColor: Palette.good)
        case .watch: return Color(nsColor: Palette.watch)
        case .off: return Color(nsColor: Palette.off)
        case .neutral, .busy: return Tok.ink3
        }
    }

    var ink: Color {
        switch self {
        case .good: return Color(nsColor: Palette.goodInk)
        case .watch: return Color(nsColor: Palette.watchInk)
        case .off: return Color(nsColor: Palette.offInk)
        case .neutral, .busy: return Tok.ink
        }
    }

    /// Text next to the dot: good news stays in the normal ink, the dot already says it.
    var text: Color {
        switch self {
        case .watch, .off: return ink
        case .good, .busy: return Tok.ink
        case .neutral: return Tok.ink2
        }
    }
}

/// A dot (or a small spinner while busy) and a line of text.
struct StatusLine: View {
    let tone: Tone
    let text: String
    var detail: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 7) {
            if tone == .busy {
                ProgressView().controlSize(.small).scaleEffect(0.6).frame(width: 9, height: 9)
                    .alignmentGuide(.firstTextBaseline) { d in d[.bottom] - 1 }
            } else {
                Circle().fill(tone.fill).frame(width: 7, height: 7)
                    .alignmentGuide(.firstTextBaseline) { d in d[.bottom] }
            }
            VStack(alignment: .leading, spacing: 1) {
                Text(text).font(.system(size: 12.5, weight: .medium)).foregroundColor(tone.text)
                    .fixedSize(horizontal: false, vertical: true)
                if let detail {
                    Text(detail).font(.system(size: 11)).foregroundColor(Tok.ink3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}

/// One part of the popover, drawn like a tile on the dashboard.
struct Card<Content: View>: View {
    let icon: String
    let tint: Color
    let title: String
    let content: Content

    init(icon: String, tint: Color, title: String, @ViewBuilder content: () -> Content) {
        self.icon = icon
        self.tint = tint
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: icon).font(.system(size: 11, weight: .semibold)).foregroundColor(tint).frame(width: 14)
                Text(title).font(.system(size: 11.5, weight: .semibold)).foregroundColor(Tok.ink3)
            }
            content
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Tok.surface))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).stroke(Tok.line, lineWidth: 1))
    }
}

/// Buttons in the dashboard's style: the accent for the one thing to do, a quiet outline for the rest.
struct AIOButtonStyle: ButtonStyle {
    enum Kind { case primary, secondary, quiet }
    var kind: Kind = .secondary

    func makeBody(configuration: Configuration) -> some View {
        StyledLabel(configuration: configuration, kind: kind)
    }

    private struct StyledLabel: View {
        let configuration: ButtonStyleConfiguration
        let kind: Kind
        @Environment(\.isEnabled) private var enabled

        var body: some View {
            configuration.label
                .font(.system(size: 12, weight: .medium))
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, kind == .quiet ? 6 : 10)
                .padding(.vertical, 5)
                .foregroundColor(foreground)
                .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(fill))
                .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).stroke(kind == .secondary ? Tok.line2 : .clear, lineWidth: 1))
                .opacity(enabled ? (configuration.isPressed ? 0.7 : 1) : 0.45)
                .contentShape(Rectangle())
        }

        private var foreground: Color {
            switch kind {
            case .primary: return Tok.onAccent
            case .secondary: return Tok.ink
            case .quiet: return Tok.ink2
            }
        }

        private var fill: Color {
            switch kind {
            case .primary: return Tok.accent
            case .secondary: return Tok.surface2
            case .quiet: return .clear
            }
        }
    }
}

extension Button {
    func aio(_ kind: AIOButtonStyle.Kind = .secondary) -> some View {
        buttonStyle(AIOButtonStyle(kind: kind))
    }
}

/// The logo in colour, as on the dashboard: a faint band and the sleep, focus and fun arcs.
struct RingLogoView: View {
    var body: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height)
            let width = side * RingLogo.lineWidth / 32
            ZStack {
                Circle().inset(by: side / 2 - side * RingLogo.radius / 32).stroke(Tok.band, lineWidth: width)
                ForEach(0..<3, id: \.self) { i in
                    RingArc(start: Double(RingLogo.arcs[i].start), end: Double(RingLogo.arcs[i].end), radius: side * RingLogo.radius / 32)
                        .stroke([Tok.sleep, Tok.focus, Tok.fun][i], style: StrokeStyle(lineWidth: width, lineCap: .round))
                }
            }
            .frame(width: side, height: side)
        }
    }
}

private struct RingArc: Shape {
    let start: Double
    let end: Double
    let radius: CGFloat

    func path(in rect: CGRect) -> Path {
        var p = Path()
        // SwiftUI's y axis points down, so "not clockwise" with growing angles turns clockwise on screen, as in the SVG
        p.addArc(center: CGPoint(x: rect.midX, y: rect.midY), radius: radius,
                 startAngle: .degrees(start), endAngle: .degrees(end), clockwise: false)
        return p
    }
}
