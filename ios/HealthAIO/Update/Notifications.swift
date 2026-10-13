import Foundation
import Observation
import UserNotifications

/// Local notifications only: one when the daily check finds something, and one scheduled for 10:00 the day
/// before the signature runs out, so the reminder comes even if the app is not opened.
@MainActor
@Observable
final class Reminders {
    static let expiryID = "signature-expiry"
    static let updateID = "update-found"

    private(set) var status: UNAuthorizationStatus = .notDetermined
    /// Shows the short explanation before iOS asks for permission.
    var showPrimer = false

    var enabled: Bool {
        didSet { defaults.set(enabled, forKey: Key.enabled) }
    }

    private let defaults: UserDefaults
    private let center = UNUserNotificationCenter.current()
    private let presenter = ForegroundPresenter()
    private var pending: (expiry: Date?, alert: Alert?)?

    struct Alert: Equatable, Sendable {
        var title: String
        var body: String
    }

    private enum Key {
        static let enabled = "reminders.enabled"
        static let primerDay = "reminders.primerShownDay"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        enabled = defaults.object(forKey: Key.enabled) as? Bool ?? true
        center.delegate = presenter
    }

    func refreshStatus() async {
        status = await center.notificationSettings().authorizationStatus
    }

    /// Called after every update check. Asks for permission (after the explanation) only when there is something
    /// to remind about.
    func apply(expiry: Date?, alert: Alert?) async {
        await refreshStatus()
        guard enabled else {
            center.removePendingNotificationRequests(withIdentifiers: [Reminders.expiryID])
            return
        }
        guard expiry != nil || alert != nil else { return }
        switch status {
        case .notDetermined:
            pending = (expiry, alert)
            let today = LocalDay.key()
            #if DEBUG
            if DebugOptions.noPrompts { return }
            #endif
            if defaults.string(forKey: Key.primerDay) != today {
                defaults.set(today, forKey: Key.primerDay)
                showPrimer = true
            }
        case .denied:
            return
        default:
            await schedule(expiry: expiry, alert: alert)
        }
    }

    func primerAccepted() async {
        showPrimer = false
        _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        await refreshStatus()
        if let pending, status == .authorized || status == .provisional {
            await schedule(expiry: pending.expiry, alert: pending.alert)
        }
        pending = nil
    }

    func primerDeclined() {
        showPrimer = false
    }

    /// The Settings toggle: turning it on for the first time goes through the same explanation.
    func setEnabled(_ on: Bool, expiry: Date?) async {
        enabled = on
        if on, status == .notDetermined {
            pending = (expiry, nil)
            showPrimer = true
        } else {
            await apply(expiry: expiry, alert: nil)
        }
    }

    private func schedule(expiry: Date?, alert: Alert?) async {
        center.removePendingNotificationRequests(withIdentifiers: [Reminders.expiryID])
        if let expiry, let when = Reminders.expiryReminderDate(expiry: expiry, now: Date()) {
            let content = UNMutableNotificationContent()
            content.title = String(localized: "Health AIO")
            content.body = String(localized: "Health AIO's signature runs out tomorrow. Open the app and tap Renew, or run healthaio iphone renew on your Mac.")
            let parts = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: when)
            let trigger = UNCalendarNotificationTrigger(dateMatching: parts, repeats: false)
            try? await center.add(UNNotificationRequest(identifier: Reminders.expiryID, content: content, trigger: trigger))
        }
        if let alert {
            let content = UNMutableNotificationContent()
            content.title = alert.title
            content.body = alert.body
            try? await center.add(UNNotificationRequest(identifier: Reminders.updateID, content: content, trigger: nil))
        }
    }

    /// 10:00 local time on the day before the signature runs out, if that is still ahead.
    nonisolated static func expiryReminderDate(expiry: Date, now: Date, calendar: Calendar = .current) -> Date? {
        guard let dayBefore = calendar.date(byAdding: .day, value: -1, to: calendar.startOfDay(for: expiry)),
              let when = calendar.date(bySettingHour: 10, minute: 0, second: 0, of: dayBefore),
              when > now
        else { return nil }
        return when
    }
}

/// Lets a notification show while the app is open (the daily check runs then).
private final class ForegroundPresenter: NSObject, UNUserNotificationCenterDelegate, Sendable {
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        [.banner, .list]
    }
}
