import AppKit

/// Update reminders. The Python side does the work (`update --check`, `update --yes`); this decides when to ask,
/// asks, and afterwards restarts the server and says what else changed.
final class UpdateManager {
    private let model: AppModel
    private let settings = AppSettings.shared
    private let progress = ProgressPanel()
    private var pending: UpdateInfo?

    var restartServer: () -> Void = {}
    var refreshStatus: () -> Void = {}

    init(model: AppModel) {
        self.model = model
    }

    /// `userInitiated`: from the button, so the answer is always shown, even "up to date" or a skipped version.
    func check(userInitiated: Bool) {
        guard !model.checkingUpdate, !model.updating else { return }
        model.checkingUpdate = true
        model.updateError = nil
        var args = ["update", "--check", "--json"]
        if userInitiated { args.append("--force") }
        CLI.shared.run(args, timeout: Timeouts.short) { [weak self] result in
            self?.checked(result, userInitiated: userInitiated)
        }
    }

    private func checked(_ result: CLIResult, userInitiated: Bool) {
        model.checkingUpdate = false
        guard let json = result.json else {
            model.updateError = result.failureText
            if userInitiated { Alerts.inform(S.checkFailedTitle, result.failureText, style: .warning) }
            return
        }
        let info = UpdateInfo(json)
        model.update = info
        if let current = info.current { model.version = current }
        if info.available, let latest = info.latest {
            AppLog.info("update \(latest) available")
            if userInitiated {
                offer(info)
            } else if latest != settings.skippedVersion {
                pending = info
                offerPendingIfIdle()
            } else {
                AppLog.info("update \(latest) was skipped by the user")
            }
        } else if userInitiated {
            if info.latest == nil, let reason = info.reason {
                Alerts.inform(S.checkFailedTitle, reason, style: .warning)
            } else {
                Alerts.inform(S.upToDateTitle, S.upToDateText(info.current ?? model.displayVersion ?? "?"))
            }
        }
    }

    /// An automatic reminder waits while another alert or a long job is on screen.
    func offerPendingIfIdle() {
        guard let info = pending, !Alerts.isShowing, !model.updating, !model.renewBusy else { return }
        pending = nil
        offer(info)
    }

    /// The popover's "Update…" button.
    func offerCurrent() {
        guard let info = model.update, info.available else {
            check(userInitiated: true)
            return
        }
        offer(info)
    }

    private func offer(_ info: UpdateInfo) {
        guard let latest = info.latest else { return }
        let alert = Self.availableAlert(info)
        switch Alerts.run(alert) {
        case .alertFirstButtonReturn:
            if info.canUpdate {
                install()
            } else if let link = info.url, let url = URL(string: link) {
                NSWorkspace.shared.open(url)
            }
        case .alertThirdButtonReturn:
            settings.skippedVersion = latest
            model.skippedVersion = latest
            AppLog.info("update \(latest) skipped")
        default:
            break
        }
    }

    /// The reminder itself; the snapshot mode draws the same alert.
    static func availableAlert(_ info: UpdateInfo) -> NSAlert {
        var text = S.youHave(info.current ?? "?")
        if let notes = info.notesExcerpt() { text += "\n\n" + notes }
        if !info.canUpdate { text += "\n\n" + S.cannotUpdateHere(info.reason ?? "?") }
        return Alerts.make(title: S.updateTitle(info.latest ?? "?"), text: text,
                           buttons: [info.canUpdate ? S.update : S.openReleasePage, S.later, S.skipThisVersion])
    }

    private func install() {
        guard !model.renewBusy else {
            Alerts.inform(S.updateFailedTitle, S.waitForRenew)
            return
        }
        model.updating = true
        model.updateError = nil
        progress.show(title: S.updatingTitle, text: S.updatingText)
        CLI.shared.run(["update", "--yes", "--json"], timeout: Timeouts.update) { [weak self] result in
            self?.installed(result)
        }
    }

    private func installed(_ result: CLIResult) {
        progress.close()
        model.updating = false
        // the new Python code only runs in a new server process
        restartServer()
        refreshStatus()

        guard let json = result.json else {
            model.updateError = result.failureText
            Alerts.inform(S.updateFailedTitle, result.failureText, style: .warning)
            return
        }
        let outcome = UpdateOutcome(json)
        guard outcome.ok else {
            let text = outcome.message ?? result.failureText
            model.updateError = text
            Alerts.inform(S.updateFailedTitle, text, style: .warning)
            return
        }
        AppLog.info("updated \(outcome.from ?? "?") → \(outcome.to ?? "?")")
        var parts: [String] = []
        if let message = outcome.message, !message.isEmpty { parts.append(message) }
        parts.append(S.dashboardRestarted)
        if outcome.macAppChanged { parts.append(S.macAppChanged) }
        if outcome.iosAppChanged { parts.append(S.iosAppChanged) }
        var buttons = [S.ok]
        if outcome.macAppChanged { buttons.append(S.showBuildScript) }
        let alert = Alerts.make(title: S.updatedTitle(outcome.to ?? "?"), text: parts.joined(separator: "\n\n"), buttons: buttons)
        if Alerts.run(alert) == .alertSecondButtonReturn, let repo = AppSettings.repoPath {
            let script = URL(fileURLWithPath: repo).appendingPathComponent("mac/build.sh")
            NSWorkspace.shared.activateFileViewerSelecting([script])
        }
    }
}
