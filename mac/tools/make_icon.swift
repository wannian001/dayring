import AppKit

/// Draws the app icon, 1024 × 1024 PNG: the dashboard's ring logo on a dusk tile, like healthaio/web/icon.svg.
/// mac/build.sh compiles this together with Sources/RingLogo.swift and turns the PNG into AppIcon.icns.
///
///     swiftc -parse-as-library mac/tools/make_icon.swift mac/Sources/RingLogo.swift -o make_icon && ./make_icon icon.png
@main
enum MakeIcon {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 2 else {
            FileHandle.standardError.write(Data("usage: make_icon OUT.png\n".utf8))
            exit(2)
        }
        let side = 1024
        guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: side, pixelsHigh: side, bitsPerSample: 8,
                                         samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                         bytesPerRow: 0, bitsPerPixel: 0),
              let context = NSGraphicsContext(bitmapImageRep: rep) else { exit(1) }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context

        // macOS icon grid: an 824-point tile centred on the 1024 canvas, with room for its shadow
        let tile = NSRect(x: 100, y: 100, width: 824, height: 824)
        let shape = NSBezierPath(roundedRect: tile, xRadius: 185, yRadius: 185)
        NSGraphicsContext.saveGraphicsState()
        let shadow = NSShadow()
        shadow.shadowColor = NSColor.black.withAlphaComponent(0.28)
        shadow.shadowOffset = NSSize(width: 0, height: -10)
        shadow.shadowBlurRadius = 24
        shadow.set()
        NSColor(srgbRed: 0x14 / 255, green: 0x18 / 255, blue: 0x22 / 255, alpha: 1).setFill()
        shape.fill()
        NSGraphicsContext.restoreGraphicsState()

        // dusk surface, slightly lighter at the top
        let gradient = NSGradient(starting: NSColor(srgbRed: 0x1d / 255, green: 0x22 / 255, blue: 0x30 / 255, alpha: 1),
                                  ending: NSColor(srgbRed: 0x10 / 255, green: 0x13 / 255, blue: 0x1b / 255, alpha: 1))
        gradient?.draw(in: shape, angle: -90)

        let ring = tile.insetBy(dx: 150, dy: 150)
        RingLogo.draw(in: ring,
                      track: NSColor(srgbRed: 0x2a / 255, green: 0x30 / 255, blue: 0x40 / 255, alpha: 1),
                      colors: [NSColor(srgbRed: 0x90 / 255, green: 0x85 / 255, blue: 0xe9 / 255, alpha: 1),
                               NSColor(srgbRed: 0x39 / 255, green: 0x87 / 255, blue: 0xe5 / 255, alpha: 1),
                               NSColor(srgbRed: 0xd9 / 255, green: 0x59 / 255, blue: 0x26 / 255, alpha: 1)])

        NSGraphicsContext.restoreGraphicsState()
        guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
        do {
            try png.write(to: URL(fileURLWithPath: args[1]))
        } catch {
            FileHandle.standardError.write(Data("cannot write \(args[1]): \(error.localizedDescription)\n".utf8))
            exit(1)
        }
    }
}
