import AppKit

/// The dashboard's logo (ICON.logo in healthaio/web/js/app.js): a ring track and three arcs for sleep, focus and
/// fun, in the same 32-unit box as the SVG so the geometry matches. mac/tools/make_icon.swift draws the app icon
/// with this file too, so it must not use anything else from Sources/.
enum RingLogo {
    /// Arcs in degrees, as in the SVG: 0 is to the right and angles grow clockwise.
    static let arcs: [(start: CGFloat, end: CGFloat)] = [(-90, -19.6), (11.5, 63.8), (83.1, 133.3)]
    static let radius: CGFloat = 12.5
    static let lineWidth: CGFloat = 5

    /// Draws into the current NSGraphicsContext, centred in `rect`.
    static func draw(in rect: CGRect, track: NSColor, colors: [NSColor], lineScale: CGFloat = 1) {
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        let scale = min(rect.width, rect.height) / 32
        let flipped = NSGraphicsContext.current?.isFlipped ?? false
        ctx.saveGState()
        ctx.translateBy(x: rect.midX, y: rect.midY)
        // y grows downwards from here on, as in the SVG
        ctx.scaleBy(x: scale, y: flipped ? scale : -scale)
        ctx.setLineWidth(lineWidth * lineScale)
        ctx.setLineCap(.round)

        ctx.setStrokeColor(track.cgColor)
        ctx.addArc(center: .zero, radius: radius, startAngle: 0, endAngle: .pi * 2, clockwise: false)
        ctx.strokePath()

        for (index, arc) in arcs.enumerated() where !colors.isEmpty {
            ctx.setStrokeColor(colors[index % colors.count].cgColor)
            ctx.addArc(center: .zero, radius: radius, startAngle: arc.start * .pi / 180, endAngle: arc.end * .pi / 180, clockwise: false)
            ctx.strokePath()
        }
        ctx.restoreGState()
    }

    /// The menu bar glyph: a template image, so macOS tints it for light and dark menu bars.
    static func statusImage(size: CGFloat = 18) -> NSImage {
        let image = NSImage(size: NSSize(width: size, height: size), flipped: false) { rect in
            draw(in: rect.insetBy(dx: 1.5, dy: 1.5), track: NSColor.black.withAlphaComponent(0.32),
                 colors: [.black], lineScale: 0.95)
            return true
        }
        image.isTemplate = true
        return image
    }
}
