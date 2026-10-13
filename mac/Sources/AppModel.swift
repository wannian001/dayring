import Foundation
import SwiftUI

/// What the popover's buttons ask for. The app controller does it; snapshots have none, so buttons do nothing.
protocol AppActions: AnyObject {
    func openDashboard()
    func collectNow()
    func openPrivacySettings()
    func renewIPhone()
    func pairIPhone()
    func checkForUpdates()
    func installUpdate()
    func openSettings()
    func chooseConfig()
    func quit()
}

/// Full Disk Access, found out by trying to list the Screen Time folder: macOS answers "not permitted" without
/// asking the user, so trying is harmless.
enum FullDiskAccess {
    enum State { case granted, denied, unknown }

    static var biomeFolder: URL {
        Paths.home.appendingPathComponent("Library/Biome/streams/restricted/App.InFocus", isDirectory: true)
    }

    static func probe() -> State {
        do {
            _ = try FileManager.default.contentsOfDirectory(atPath: biomeFolder.path)
            return .granted
        } catch {
            let ns = error as NSError
            if ns.domain == NSCocoaErrorDomain && ns.code == NSFileReadNoPermissionError { return .denied }
            if let underlying = ns.userInfo[NSUnderlyingErrorKey] as? NSError, underlying.domain == NSPOSIXErrorDomain,
               underlying.code == Int(EPERM) || underlying.code == Int(EACCES) {
                return .denied
            }
            return .unknown // no such folder: Screen Time is off, or this is not the Mac it syncs to
        }
    }
}

/// Everything the popover shows. Changed on the main thread only.
final class AppModel: ObservableObject {
    weak var actions: AppActions?

    @Published var now = Date()
    @Published var setupProblem: String?
    @Published var statusError: String?

    @Published var server: ServerSupervisor.State = .stopped
    @Published var serverLAN = false
    @Published var port = AppSettings.defaultPort

    @Published var version: String?
    @Published var fda: FullDiskAccess.State = .unknown
    @Published var collect: CollectResult?
    @Published var collecting = false
    @Published var collectError: String?
    @Published var nextCollect: Date?
    @Published var collectEveryHours = AppSettings.defaultCollectHours

    @Published var devices: [Device] = []
    @Published var iphone: IPhoneInfo?
    @Published var renewing = false
    @Published var renewError: String?

    @Published var update: UpdateInfo?
    @Published var updateError: String?
    @Published var checkingUpdate = false
    @Published var updating = false
    @Published var skippedVersion: String?

    // MARK: derived

    var displayVersion: String? {
        version ?? update?.current ?? (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String)
    }

    var serverUp: Bool { server == .running || server == .external }

    var serverTone: Tone {
        switch server {
        case .running, .external: return .good
        case .starting: return .busy
        case .stopped: return .neutral
        case .blocked: return setupProblem == nil ? .off : .neutral
        case .retrying: return .off
        }
    }

    var serverText: String {
        switch server {
        case .running: return S.running
        case .external: return S.runningElsewhere
        case .starting: return S.starting
        case .stopped: return S.stopped
        case .blocked(let why): return setupProblem == nil ? why : S.stopped
        case .retrying(let at, _): return S.retrying(max(1, Int(at.timeIntervalSince(now).rounded(.up))))
        }
    }

    var serverDetail: String? {
        switch server {
        case .running: return "localhost:\(port) · " + (serverLAN ? S.phonesCanConnect : S.thisMacOnly)
        case .external, .starting: return "localhost:\(port)"
        case .retrying(_, let line): return line.isEmpty ? nil : line
        case .stopped, .blocked: return nil
        }
    }

    var signatureExpiry: Date? { iphone?.last?.expiresAt }

    /// Two days or less: time to renew (the badge on the menu bar icon and the daily reminder).
    var needsRenew: Bool {
        guard let expiry = signatureExpiry else { return false }
        return expiry.timeIntervalSince(now) <= 2 * 86400
    }

    var signatureExpired: Bool {
        guard let expiry = signatureExpiry else { return false }
        return expiry <= now
    }

    var renewBusy: Bool { renewing || (iphone?.running ?? false) }
    var canRenew: Bool { (iphone?.canRenew ?? false) && !renewBusy && !updating }
    var renewBlockedReason: String? {
        guard let info = iphone, !info.canRenew else { return nil }
        return S.renewReason(info.reason)
    }

    var updateAvailable: Bool { update?.available ?? false }
}
