import AppKit
import SwiftUI

/// One alert at a time. Reminders that arrive while one is open wait for the next look at the clock.
enum Alerts {
    private(set) static var isShowing = false

    @discardableResult
    static func run(_ alert: NSAlert) -> NSApplication.ModalResponse {
        isShowing = true
        defer { isShowing = false }
        App.activate()
        alert.window.level = .floating
        return alert.runModal()
    }

    static func make(title: String, text: String, buttons: [String], style: NSAlert.Style = .informational) -> NSAlert {
        let alert = NSAlert()
        alert.alertStyle = style
        alert.messageText = title
        alert.informativeText = text
        for title in buttons { alert.addButton(withTitle: title) }
        return alert
    }

    static func inform(_ title: String, _ text: String, style: NSAlert.Style = .informational) {
        run(make(title: title, text: text, buttons: [S.ok], style: style))
    }
}

/// A small window with a spinner while a long job runs (the update).
final class ProgressPanel {
    private var window: NSWindow?

    func show(title: String, text: String) {
        let view = VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                ProgressView().controlSize(.small)
                Text(title).font(.system(size: 13, weight: .semibold))
            }
            Text(text).font(.system(size: 12)).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        .padding(20)
        .frame(width: 340, alignment: .leading)
        let host = NSHostingController(rootView: view)
        let window = NSWindow(contentViewController: host)
        window.styleMask = [.titled]
        window.title = "Health AIO"
        window.level = .floating
        window.isReleasedWhenClosed = false
        window.center()
        App.activate()
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    func close() {
        window?.orderOut(nil)
        window = nil
    }
}
