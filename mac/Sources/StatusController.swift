import AppKit
import Combine
import SwiftUI

/// The menu bar icon and its popover. A dot on the icon means the iPhone app's signature runs out within two days.
final class StatusController: NSObject, NSPopoverDelegate {
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    private let popover = NSPopover()
    private let model: AppModel
    private let badge = BadgeView(frame: NSRect(x: 0, y: 0, width: 7, height: 7))
    private var observer: AnyCancellable?

    /// Called just before the popover opens, to refresh what it shows.
    var onOpen: (() -> Void)?

    init(model: AppModel) {
        self.model = model
        super.init()
        if let button = item.button {
            button.image = RingLogo.statusImage()
            button.imagePosition = .imageOnly
            button.target = self
            button.action = #selector(toggle(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
            badge.isHidden = true
            button.addSubview(badge)
        }
        item.isVisible = true

        let host = NSHostingController(rootView: PopoverView(model: model))
        host.sizingOptions = [.preferredContentSize]
        popover.contentViewController = host
        popover.behavior = .transient
        popover.animates = true
        popover.delegate = self

        // objectWillChange fires before the change lands; look one turn of the run loop later.
        observer = model.objectWillChange.sink { [weak self] _ in
            DispatchQueue.main.async { self?.refresh() }
        }
        refresh()
    }

    var buttonFrameOnScreen: NSRect? {
        guard let button = item.button, let window = button.window else { return nil }
        return window.convertToScreen(button.convert(button.bounds, to: nil))
    }

    var popoverWindow: NSWindow? { popover.contentViewController?.view.window }
    var isShown: Bool { popover.isShown }

    @objc private func toggle(_ sender: Any?) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            show()
        }
    }

    func show() {
        guard let button = item.button else { return }
        model.now = Date()
        onOpen?()
        App.activate()
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        popover.contentViewController?.view.window?.makeKey()
    }

    func close() {
        if popover.isShown { popover.performClose(nil) }
    }

    private func refresh() {
        guard let button = item.button else { return }
        badge.isHidden = !model.needsRenew
        badge.color = model.signatureExpired ? Palette.off : Palette.watch
        let size = badge.frame.size
        let y = button.isFlipped ? 2 : button.bounds.height - size.height - 2
        badge.setFrameOrigin(NSPoint(x: button.bounds.width - size.width - 1, y: y))
        button.appearsDisabled = !(model.serverUp || model.server == .starting)
        var tip = "Health AIO · " + model.serverText
        if model.needsRenew, let expiry = model.signatureExpiry {
            tip += "\n" + (model.signatureExpired ? S.signatureGone : S.signatureLeft(TimeText.remaining(expiry, now: model.now)))
        }
        button.toolTip = tip
    }
}

/// A small filled circle. Drawn by hand because a template image cannot carry colour.
final class BadgeView: NSView {
    var color: NSColor = Palette.watch {
        didSet { needsDisplay = true }
    }

    override func draw(_ dirtyRect: NSRect) {
        color.setFill()
        NSBezierPath(ovalIn: bounds).fill()
    }
}
