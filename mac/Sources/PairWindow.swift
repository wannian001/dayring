import AppKit
import CoreImage
import CoreImage.CIFilterBuiltins
import SwiftUI

/// The pairing window: `pair --json` opens an 8-digit code for 10 minutes; the phone scans the QR code of its link
/// (or the code is typed by hand). While the window is open, a new device in `devices --json` means it worked.
final class PairModel: ObservableObject {
    @Published private(set) var info: PairInfo?
    @Published private(set) var qrImage: NSImage?
    @Published var loading = false
    @Published var error: String?
    @Published var now = Date()
    @Published var pairedName: String?
    /// Fallback when the answer has no expires_at: the contract's 10 minutes from when it came.
    @Published var receivedAt = Date()

    var onNewCode: () -> Void = {}
    var onLetConnect: () -> Void = {}
    var onDone: () -> Void = {}

    func show(_ info: PairInfo?) {
        self.info = info
        qrImage = info.flatMap { QRCode.image(for: $0.link) }
    }

    var expiresAt: Date { info?.expiresAt ?? receivedAt.addingTimeInterval(600) }
    var secondsLeft: Int { max(0, Int(expiresAt.timeIntervalSince(now).rounded(.down))) }
    var expired: Bool { info != nil && secondsLeft == 0 && pairedName == nil }
    var phonesCanReach: Bool { (info?.serverRunning ?? true) && (info?.serverLAN ?? true) }
}

struct PairView: View {
    @ObservedObject var model: PairModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 8) {
                RingLogoView().frame(width: 22, height: 22)
                Text(S.pairHeading).font(.system(size: 17, weight: .semibold)).foregroundColor(Tok.ink)
            }
            HStack(alignment: .top, spacing: 20) {
                qr
                details
            }
            if let info = model.info, !model.phonesCanReach, model.pairedName == nil {
                warning(info)
            }
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "wifi").font(.system(size: 12, weight: .semibold)).foregroundColor(Tok.accent)
                Text(S.pairHint).font(.system(size: 12)).foregroundColor(Tok.ink2).fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button(S.newCode) { model.onNewCode() }.aio().disabled(model.loading)
                Button(S.done) { model.onDone() }.aio(.primary).keyboardShortcut(.defaultAction)
            }
        }
        .padding(22)
        .frame(width: 560, alignment: .leading)
        .background(Tok.bg)
    }

    private var qr: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Color.white)
            if let image = model.qrImage {
                Image(nsImage: image).interpolation(.none).resizable().frame(width: 196, height: 196)
                    .opacity(model.expired ? 0.12 : 1)
            } else if model.loading {
                ProgressView().controlSize(.small)
            }
            if model.pairedName != nil {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 64)).foregroundColor(Tone.good.fill)
                    .background(Circle().fill(Color.white).padding(4))
            }
        }
        .frame(width: 220, height: 220)
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Tok.line, lineWidth: 1))
    }

    private var details: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(S.code).font(.system(size: 11.5, weight: .semibold)).foregroundColor(Tok.ink3)
                Text(model.info?.groupedCode ?? "···· ····")
                    .font(.system(size: 40, weight: .semibold, design: .monospaced))
                    .foregroundColor(model.expired ? Tok.ink3 : Tok.ink)
                    .strikethrough(model.expired)
                    .textSelection(.enabled)
                status
            }
            if let urls = model.info?.urls, !urls.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    Text(S.addresses).font(.system(size: 11.5, weight: .semibold)).foregroundColor(Tok.ink3)
                    ForEach(urls, id: \.self) { url in
                        Text(url).font(.system(size: 12, design: .monospaced)).foregroundColor(Tok.ink2).textSelection(.enabled)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder private var status: some View {
        if let name = model.pairedName {
            StatusLine(tone: .good, text: S.paired(name))
        } else if let error = model.error {
            Text(error).font(.system(size: 11.5)).foregroundColor(Tone.off.ink).lineLimit(6)
                .fixedSize(horizontal: false, vertical: true)
        } else if model.loading {
            StatusLine(tone: .busy, text: S.gettingCode)
        } else if model.expired {
            StatusLine(tone: .off, text: S.codeExpired)
        } else if model.info != nil {
            StatusLine(tone: .good, text: S.codeWorks(TimeText.countdown(model.secondsLeft)))
        }
    }

    private func warning(_ info: PairInfo) -> some View {
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundColor(Tone.watch.fill)
            Text(info.serverRunning ? S.pairNeedsLAN : S.pairServerDown).font(.system(size: 12, weight: .medium))
                .foregroundColor(Tone.watch.ink).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 4)
            if info.serverRunning && !info.serverLAN {
                Button(S.letPhoneConnect) { model.onLetConnect() }.aio(.primary)
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Tok.watchSoft))
    }
}

enum QRCode {
    /// Black on white whatever the appearance: phone cameras read that best.
    static func image(for text: String, pixels: CGFloat = 392) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage, output.extent.width > 0 else { return nil }
        let scale = max(1, (pixels / output.extent.width).rounded(.down))
        let scaled = output.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        guard let cg = CIContext().createCGImage(scaled, from: scaled.extent) else { return nil }
        return NSImage(cgImage: cg, size: NSSize(width: scaled.extent.width / 2, height: scaled.extent.height / 2))
    }
}

final class PairWindowController: NSWindowController, NSWindowDelegate {
    let model = PairModel()
    private var timer: Timer?
    private var ticks = 0
    private var knownDevices: Set<String> = []
    private var polling = false

    var onLetConnect: () -> Void = {}
    var onClose: () -> Void = {}

    init() {
        let host = NSHostingController(rootView: PairView(model: model))
        let window = NSWindow(contentViewController: host)
        window.styleMask = [.titled, .closable]
        window.title = S.pairTitle
        window.isReleasedWhenClosed = false
        super.init(window: window)
        window.delegate = self
        model.onNewCode = { [weak self] in self?.requestCode() }
        model.onDone = { [weak self] in self?.close() }
        model.onLetConnect = { [weak self] in
            self?.onLetConnect()
            // give the server a moment to come back with --lan before asking for a fresh code
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { self?.requestCode() }
        }
    }

    required init?(coder: NSCoder) { nil }

    func present() {
        window?.center()
        App.activate()
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        if timer == nil {
            let timer = Timer(timeInterval: 1, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
            RunLoop.main.add(timer, forMode: .common)
            self.timer = timer
        }
        requestCode()
    }

    func requestCode() {
        guard !model.loading else { return }
        model.loading = true
        model.error = nil
        model.pairedName = nil
        // remember who is paired already, so a new name means this pairing worked
        CLI.shared.run(["devices", "--json"], timeout: Timeouts.short) { [weak self] result in
            guard let self else { return }
            self.knownDevices = Set(Device.list(result.json).map(\.id))
            CLI.shared.run(["pair", "--json"], timeout: Timeouts.short) { [weak self] result in
                self?.received(result)
            }
        }
    }

    private func received(_ result: CLIResult) {
        model.loading = false
        model.now = Date()
        model.receivedAt = Date()
        if let info = PairInfo(result.json) {
            model.show(info)
        } else {
            model.show(nil)
            model.error = result.json?.string("error") ?? result.failureText
        }
    }

    @objc private func tick() {
        model.now = Date()
        ticks += 1
        guard ticks % 3 == 0, model.info != nil, model.pairedName == nil, !model.expired, !polling else { return }
        polling = true
        CLI.shared.run(["devices", "--json"], timeout: Timeouts.short) { [weak self] result in
            guard let self else { return }
            self.polling = false
            guard result.json != nil else { return }
            if let fresh = Device.list(result.json).first(where: { !self.knownDevices.contains($0.id) }) {
                self.model.pairedName = fresh.name
                AppLog.info("a device paired")
            }
        }
    }

    func windowWillClose(_ notification: Notification) {
        timer?.invalidate()
        timer = nil
        onClose()
    }
}
