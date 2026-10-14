import AppKit
import SwiftUI

/// `HealthAIO --snapshot <dir>` draws the popover, the pairing window, the settings window and the update alert
/// with made-up data, in light and dark and in both languages, into PNG files, then exits. Nothing is run and
/// nothing is read from this Mac. HEALTHAIO_MAC_SELFTEST=<dir> instead opens the real popover once after launch
/// and saves what it shows (a development check).
enum Snapshot {
    /// 2026-10-13 21:12 in Melbourne: the made-up "now" every picture is drawn at.
    static let now = ISODate.parse("2026-10-13T21:12:00+11:00") ?? Date()

    static func run(into dir: String) -> Int32 {
        _ = NSApplication.shared
        NSApp.setActivationPolicy(.accessory)
        TimeText.timeZone = TimeZone(identifier: "Australia/Melbourne") ?? .current
        let out = URL(fileURLWithPath: dir, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        } catch {
            FileHandle.standardError.write(Data("cannot create \(dir): \(error.localizedDescription)\n".utf8))
            return 1
        }
        let modes: [(String, NSAppearance.Name)] = [("light", .aqua), ("dark", .darkAqua)]
        var written: [URL] = []
        for (lang, chinese) in [("en", false), ("zh", true)] {
            Lang.chinese = chinese
            for (mode, appearance) in modes {
                let name = { (what: String) in out.appendingPathComponent("\(what)-\(lang)-\(mode).png") }
                written.append(render(PopoverView(model: normalModel()), appearance: appearance, popover: true, to: name("popover-normal")))
                written.append(render(PopoverView(model: attentionModel()), appearance: appearance, popover: true, to: name("popover-attention")))
                written.append(render(PairView(model: pairModel()), appearance: appearance, popover: false, to: name("pair")))
                written.append(renderAlert(UpdateManager.availableAlert(sampleUpdate()), appearance: appearance, to: name("update-alert")))
                written.append(render(SettingsView(draft: settingsDraft()), appearance: appearance, popover: false, to: name("settings")))
            }
        }
        written.append(renderGlyphs(to: out.appendingPathComponent("status-item.png")))
        for url in written { print(url.path) }
        return 0
    }

    // MARK: made-up data

    static func normalModel() -> AppModel {
        let m = AppModel()
        m.now = now
        m.server = .running
        m.serverLAN = true
        m.version = "0.3.0"
        m.fda = .granted
        m.collect = CollectResult([
            "ok": true, "at": "2026-10-13T21:00:02+11:00",
            "sources": [["name": "macos-screentime", "ok": true, "message": "412 sessions on 3 devices"]],
        ])
        m.nextCollect = now.addingTimeInterval(108 * 60)
        m.devices = Device.list(["devices": [["id": "demo-device-1", "name": "iPhone",
                                              "paired_at": "2026-10-11T19:30:00+11:00", "last_seen": "2026-10-13T20:52:00+11:00"]]])
        m.iphone = IPhoneInfo(["can_renew": true, "running": false,
                               "last": ["at": "2026-10-11T20:05:00+11:00", "ok": true, "expires_at": "2026-10-18T20:05:00+11:00",
                                        "version": "0.3.0", "message": "Installed on iPhone"]])
        m.update = UpdateInfo(["current": "0.3.0", "latest": "0.3.0", "update_available": false,
                               "checked_at": "2026-10-13T09:14:00+11:00", "install": "git", "can_update": true])
        return m
    }

    /// Full Disk Access missing, an update waiting and one day of signature left.
    static func attentionModel() -> AppModel {
        let m = AppModel()
        m.now = now
        m.server = .running
        m.serverLAN = false
        m.version = "0.3.0"
        m.fda = .denied
        m.collect = CollectResult([
            "ok": false, "at": "2026-10-13T19:00:04+11:00",
            "sources": [["name": "macos-screentime", "ok": false, "message": "Full Disk Access is needed to read Screen Time."]],
        ])
        m.nextCollect = now.addingTimeInterval(108 * 60)
        m.devices = Device.list(["devices": [["id": "demo-device-1", "name": "iPhone",
                                              "paired_at": "2026-10-06T19:30:00+11:00", "last_seen": "2026-10-11T22:40:00+11:00"]]])
        m.iphone = IPhoneInfo(["can_renew": true, "running": false,
                               "last": ["at": "2026-10-07T23:40:00+11:00", "ok": true, "expires_at": "2026-10-15T02:40:00+11:00",
                                        "version": "0.3.0", "message": "Installed on iPhone"]])
        m.update = UpdateInfo(sampleUpdateJSON)
        return m
    }

    static let sampleUpdateJSON: JSONObject = [
        "current": "0.3.0", "latest": "0.3.1", "update_available": true,
        "url": "https://github.com/wannian001/proactive-health-aio/releases/tag/v0.3.1",
        "notes": """
        Screen Time: a Mac and an iPhone used at the same time are counted once.
        The iPhone app can catch up 14 days in one go.
        Goals: a plan you have not set says how to set it.
        Food: fibre is compared with your plan.
        Schedule: deadlines show their share of the grade.
        Faster start on large data folders.
        Smaller fixes.
        """,
        "checked_at": "2026-10-13T09:14:00+11:00", "install": "git", "can_update": true,
    ]

    static func sampleUpdate() -> UpdateInfo { UpdateInfo(sampleUpdateJSON) }

    static func pairModel() -> PairModel {
        let m = PairModel()
        m.now = now
        m.receivedAt = now
        m.show(PairInfo([
            "code": "48213907", "expires_at": "2026-10-13T21:21:41+11:00",
            "urls": ["http://192.168.1.20:8790", "http://10.0.0.20:8790"],
            "link": "healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907",
            "server_running": true, "server_lan": true,
        ]))
        return m
    }

    static func settingsDraft() -> SettingsDraft {
        let draft = SettingsDraft(settings: AppSettings.shared, openAtLogin: true,
                                  repoPath: "~/proactive-health-aio", defaultPython: "/usr/bin/python3")
        draft.configPath = "~/Health/healthaio.toml"
        draft.pythonPath = "/usr/bin/python3"
        draft.lan = true
        draft.portText = "8790"
        draft.collectHours = 2
        draft.autoUpdate = true
        return draft
    }

    // MARK: drawing

    /// Popover pictures get the window background behind them, as the real popover has its own material there.
    private static func render<V: View>(_ view: V, appearance: NSAppearance.Name, popover: Bool, to url: URL) -> URL {
        let root = view.background(popover ? Color(nsColor: .windowBackgroundColor) : Color.clear)
        let host = NSHostingView(rootView: root)
        let window = NSWindow(contentRect: .zero, styleMask: [.borderless], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: appearance)
        window.contentView = host
        let size = host.fittingSize
        window.setContentSize(size)
        host.frame = NSRect(origin: .zero, size: size)
        host.layoutSubtreeIfNeeded()
        if !popover {
            // a window's own background, which the SwiftUI view does not paint everywhere
            host.wantsLayer = true
            host.layer?.backgroundColor = resolved(.windowBackgroundColor, appearance).cgColor
        }
        write(view: host, to: url)
        return url
    }

    private static func renderAlert(_ alert: NSAlert, appearance: NSAppearance.Name, to url: URL) -> URL {
        alert.window.appearance = NSAppearance(named: appearance)
        alert.layout()
        if let view = alert.window.contentView {
            view.wantsLayer = true
            view.layer?.backgroundColor = resolved(.windowBackgroundColor, appearance).cgColor
            write(view: view, to: url)
        }
        return url
    }

    private static func resolved(_ color: NSColor, _ appearance: NSAppearance.Name) -> NSColor {
        var result = color
        NSAppearance(named: appearance)?.performAsCurrentDrawingAppearance {
            result = color.usingColorSpace(.sRGB) ?? color
        }
        return result
    }

    static func write(view: NSView, to url: URL, scale: CGFloat = 2) {
        let size = view.bounds.size
        guard size.width > 0, size.height > 0,
              let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width * scale), pixelsHigh: Int(size.height * scale),
                                         bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                         colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return }
        rep.size = size
        view.cacheDisplay(in: view.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }

    /// The menu bar glyph on a light and a dark menu bar, without and with the renew dot.
    private static func renderGlyphs(to url: URL) -> URL {
        let cell: CGFloat = 30
        let size = NSSize(width: cell * 4, height: cell)
        let glyph = RingLogo.statusImage()
        let image = NSImage(size: size, flipped: false) { _ in
            let cases: [(NSColor, NSColor, Bool)] = [
                (NSColor(white: 0.93, alpha: 1), .black, false), (NSColor(white: 0.93, alpha: 1), .black, true),
                (NSColor(white: 0.16, alpha: 1), .white, false), (NSColor(white: 0.16, alpha: 1), .white, true),
            ]
            for (i, (bg, fg, dot)) in cases.enumerated() {
                let rect = NSRect(x: CGFloat(i) * cell, y: 0, width: cell, height: cell)
                bg.setFill()
                rect.fill()
                let tinted = NSImage(size: glyph.size, flipped: false) { r in
                    glyph.draw(in: r)
                    fg.setFill()
                    r.fill(using: .sourceAtop)
                    return true
                }
                let g = NSRect(x: rect.midX - 9, y: rect.midY - 9, width: 18, height: 18)
                tinted.draw(in: g)
                if dot {
                    Palette.watch.setFill()
                    NSBezierPath(ovalIn: NSRect(x: g.maxX - 6, y: g.maxY - 7, width: 7, height: 7)).fill()
                }
            }
            return true
        }
        let view = NSImageView(frame: NSRect(origin: .zero, size: size))
        view.image = image
        view.imageScaling = .scaleNone
        write(view: view, to: url)
        return url
    }

    // MARK: self-test

    static func selfTest(status: StatusController, into dir: String) {
        let out = URL(fileURLWithPath: dir, isDirectory: true)
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
            AppLog.info("selftest: status item frame \(status.buttonFrameOnScreen.map { NSStringFromRect($0) } ?? "none")")
            status.show()
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                if let window = status.popoverWindow, let view = window.contentView {
                    AppLog.info("selftest: popover shown \(status.isShown), frame \(NSStringFromRect(window.frame))")
                    write(view: view, to: out.appendingPathComponent("selftest-popover.png"))
                } else {
                    AppLog.info("selftest: no popover window")
                }
                status.close()
                if ProcessInfo.processInfo.environment["HEALTHAIO_MAC_SELFTEST_QUIT"] == "1" {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) { NSApp.terminate(nil) }
                }
            }
        }
    }
}
