import Foundation
import Observation

/// Why the banner shows. Renewing the signature is the main job; a newer version rides along with it.
enum BannerReason: Equatable, Sendable {
    case signature(daysLeft: Int, expiry: Date)
    case newVersion(String)

    static let warnBefore: TimeInterval = 2 * 24 * 3600

    static func reasons(expiry: Date?, now: Date, appVersion: String, latest: [String?]) -> [BannerReason] {
        var reasons: [BannerReason] = []
        if let expiry, expiry.timeIntervalSince(now) <= warnBefore {
            let days = max(0, Int((expiry.timeIntervalSince(now) / 86400).rounded(.up)))
            reasons.append(.signature(daysLeft: days, expiry: expiry))
        }
        let newer = latest.compactMap { $0 }
            .filter { SemVer.isNewer($0, than: appVersion) }
            .compactMap(SemVer.init)
        if let best = newer.max() {
            reasons.append(.newVersion("v" + best.description))
        }
        return reasons
    }
}

/// The daily check: the app's own signature, GitHub's latest release and the computer's status, once per local
/// day on the first time the app comes to the front. Also runs "Renew now".
@MainActor
@Observable
final class UpdateCenter {
    private(set) var expiry: Date?
    private(set) var githubLatest: String?
    private(set) var computerVersion: String?
    private(set) var computerRenew: RenewState?
    private(set) var lastCheckedAt: Date?
    private(set) var isChecking = false
    private(set) var reasons: [BannerReason] = []
    private(set) var renew: RenewProgress = .idle
    private var dismissedDay: String?

    private let defaults: UserDefaults
    private let reminders: Reminders
    private var pollTask: Task<Void, Never>?

    enum RenewProgress: Equatable, Sendable {
        case idle
        case asking
        case running(message: String?)
        case finished(ok: Bool, message: String?)
        case cannot(reason: String?, message: String?)
        case failed(String)
    }

    private enum Key {
        static let checkDay = "update.checkDay"
        static let dismissedDay = "update.dismissedDay"
        static let github = "update.githubLatest"
        static let computer = "update.computerVersion"
        static let checkedAt = "update.checkedAt"
    }

    init(defaults: UserDefaults = .standard, reminders: Reminders) {
        self.defaults = defaults
        self.reminders = reminders
        githubLatest = defaults.string(forKey: Key.github)
        computerVersion = defaults.string(forKey: Key.computer)
        lastCheckedAt = defaults.object(forKey: Key.checkedAt) as? Date
        dismissedDay = defaults.string(forKey: Key.dismissedDay)
        expiry = UpdateCenter.signatureExpiry()
        recompute()
    }

    static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
    }

    static var appBuild: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
    }

    static func signatureExpiry() -> Date? {
        #if DEBUG
        if let pretend = DebugOptions.expiry { return pretend }
        #endif
        return ProvisioningProfile.embedded()?.expirationDate
    }

    var showBanner: Bool {
        if case .running = renew { return true }
        return !reasons.isEmpty && dismissedDay != LocalDay.key()
    }

    func dismissForToday() {
        dismissedDay = LocalDay.key()
        defaults.set(dismissedDay, forKey: Key.dismissedDay)
        if case .running = renew { return }
        renew = .idle
    }

    /// Runs the check the first time the app is in front on a new local day.
    func dailyCheckIfNeeded(client: ServerClient?) {
        recompute()
        let today = LocalDay.key()
        guard defaults.string(forKey: Key.checkDay) != today else { return }
        defaults.set(today, forKey: Key.checkDay)
        Task { await check(client: client, notify: true) }
    }

    func check(client: ServerClient?, notify: Bool) async {
        guard !isChecking else { return }
        isChecking = true
        defer { isChecking = false }
        expiry = UpdateCenter.signatureExpiry()
        if let tag = await GitHubReleases.latestTag() {
            githubLatest = tag
            defaults.set(tag, forKey: Key.github)
        }
        if let client, let status = try? await client.status() {
            note(status: status)
        }
        lastCheckedAt = Date()
        defaults.set(lastCheckedAt, forKey: Key.checkedAt)
        recompute()
        await reminders.apply(expiry: expiry, alert: notify ? alert() : nil)
    }

    /// The Capture tab also reads `/capture/v1/status`; whatever it learns about versions lands here too.
    func note(status: ServerStatus) {
        if let version = status.version {
            computerVersion = version
            defaults.set(version, forKey: Key.computer)
        }
        computerRenew = status.iphone
        recompute()
    }

    private func recompute() {
        reasons = BannerReason.reasons(expiry: expiry, now: Date(), appVersion: UpdateCenter.appVersion,
                                       latest: [githubLatest, computerVersion])
    }

    private func alert() -> Reminders.Alert? {
        guard !reasons.isEmpty else { return nil }
        return Reminders.Alert(title: String(localized: "Health AIO"),
                               body: reasons.map(Strings.bannerLine).joined(separator: " "))
    }

    // MARK: Renew

    /// Asks the computer to build, sign and install the app again, then follows its progress every 5 seconds.
    func renewNow(client: ServerClient?) {
        guard let client else {
            renew = .failed(ServerError.notPaired.localizedDescription)
            return
        }
        pollTask?.cancel()
        renew = .asking
        pollTask = Task {
            do {
                switch try await client.startRenew() {
                case .started, .alreadyRunning:
                    renew = .running(message: nil)
                    await poll(client)
                case .cannot(let reason, let message):
                    renew = .cannot(reason: reason, message: message)
                }
            } catch {
                renew = .failed(error.localizedDescription)
            }
        }
    }

    private func poll(_ client: ServerClient) async {
        let started = Date()
        var misses = 0
        while !Task.isCancelled, Date().timeIntervalSince(started) < 30 * 60 {
            try? await Task.sleep(for: .seconds(5))
            guard let state = try? await client.renewState() else {
                misses += 1
                if misses >= 6 {
                    renew = .failed(ServerError.unreachable("").localizedDescription)
                    return
                }
                continue
            }
            misses = 0
            computerRenew = state
            if state.running == true {
                renew = .running(message: state.last?.message)
                continue
            }
            renew = .finished(ok: state.last?.ok ?? false, message: state.last?.message)
            return
        }
    }
}
