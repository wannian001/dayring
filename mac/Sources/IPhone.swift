import AppKit

/// The iPhone app's 7-day signature: renewing it (`iphone renew`, which builds and installs with Xcode) and the
/// once-a-day reminder when two days or less are left.
final class IPhoneManager {
    private let model: AppModel
    private let settings = AppSettings.shared

    var refreshStatus: () -> Void = {}

    init(model: AppModel) {
        self.model = model
    }

    func renew() {
        guard !model.renewBusy else { return }
        guard !model.updating else {
            Alerts.inform(S.renewFailedTitle, S.waitForUpdate)
            return
        }
        if let info = model.iphone, !info.canRenew {
            Alerts.inform(S.cannotRenewTitle, S.renewReason(info.reason) ?? "")
            return
        }
        model.renewing = true
        model.renewError = nil
        CLI.shared.run(["iphone", "renew", "--json"], timeout: Timeouts.renew) { [weak self] result in
            self?.renewed(result)
        }
    }

    private func renewed(_ result: CLIResult) {
        model.renewing = false
        refreshStatus()
        guard let json = result.json else {
            model.renewError = result.failureText
            Alerts.inform(S.renewFailedTitle, result.failureText, style: .warning)
            return
        }
        let outcome = RenewOutcome(json)
        if outcome.ok {
            AppLog.info("iPhone app renewed")
            var text = outcome.expiresAt.map { S.renewedText(TimeText.day($0) + " " + TimeText.clock($0)) } ?? ""
            if let message = outcome.message, !message.isEmpty { text += (text.isEmpty ? "" : "\n\n") + message }
            Alerts.inform(S.renewedTitle, text)
        } else {
            let text = outcome.message ?? result.failureText
            model.renewError = text
            Alerts.inform(S.renewFailedTitle, text, style: .warning)
        }
    }

    /// After every status read: remind once a day while the signature has two days or less.
    func checkSignature() {
        guard model.needsRenew, let expiry = model.signatureExpiry,
              !Alerts.isShowing, !model.renewBusy, !model.updating else { return }
        let today = Self.dayKey(Date())
        guard settings.signatureAlertDay != today else { return }
        settings.signatureAlertDay = today
        AppLog.info("signature reminder shown")

        let title = model.signatureExpired ? S.signatureExpiredTitle : S.signatureAlertTitle(TimeText.remaining(expiry, now: Date()))
        if let reason = model.renewBlockedReason {
            Alerts.inform(title, S.signatureAlertText + "\n\n" + reason, style: .warning)
            return
        }
        let alert = Alerts.make(title: title, text: S.signatureAlertText, buttons: [S.renewNow, S.later], style: .warning)
        if Alerts.run(alert) == .alertFirstButtonReturn { renew() }
    }

    private static func dayKey(_ date: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }
}
