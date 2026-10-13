import Foundation
import Observation

enum AppTab: String, Hashable, Sendable {
    case panel, capture, settings
}

/// Holds the app's parts and the few decisions that span tabs (pairing links, coming to the front).
@MainActor
@Observable
final class AppModel {
    var tab: AppTab = .panel
    /// A pairing link that arrived from the Camera or a paste, waiting for the user to confirm.
    var pendingLink: PairingLink?
    var pairingError: String?
    private(set) var isPairing = false

    let connection: Connection
    let reminders: Reminders
    let updates: UpdateCenter
    let sync: SyncEngine

    init() {
        connection = Connection()
        reminders = Reminders()
        updates = UpdateCenter(reminders: reminders)
        sync = SyncEngine(connection: connection, updates: updates)
        #if DEBUG
        if let tab = DebugOptions.tab.flatMap(AppTab.init(rawValue:)) { self.tab = tab }
        #endif
    }

    /// Each time the app comes to the front: the daily update check (once per local day) and, a second later,
    /// a read of the last 3 days. Neither blocks the UI.
    func becameActive() {
        sync.becameActive()
        updates.dailyCheckIfNeeded(client: connection.client())
        Task { await reminders.refreshStatus() }
    }

    func open(_ url: URL) {
        if let link = PairingLink.parse(url.absoluteString) {
            pendingLink = link
            tab = .settings
        }
    }

    func pair(_ link: PairingLink) async {
        guard !isPairing else { return }
        isPairing = true
        pairingError = nil
        defer { isPairing = false }
        do {
            try await connection.pair(with: link)
            await sync.refreshComputer()
            await updates.check(client: connection.client(), notify: false)
        } catch {
            pairingError = error.localizedDescription
        }
    }

    func unpair() async {
        await connection.unpair()
    }

    #if DEBUG
    /// `-HealthAIODebugServer` and `-HealthAIODebugPairCode`: pair on launch unless already paired with that address.
    /// `-HealthAIODebugSendSample YES`: then post the made-up sample package once, through the normal outbox.
    func debugLaunchActions() async {
        if let link = DebugOptions.pairingLink, connection.serverURL != link.serverURL {
            await pair(link)
        }
        if DebugOptions.sendSample, connection.isPaired {
            await sync.sendSample()
        }
    }
    #endif
}
