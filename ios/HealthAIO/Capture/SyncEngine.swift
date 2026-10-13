import Foundation
import Observation

/// What the last read of Apple Health found and what became of it.
struct ReadSummary: Codable, Equatable, Sendable {
    enum Outcome: String, Codable, Sendable {
        case sent, nothingNew, empty, blocked, failed
    }

    var at: Date
    var startDate: String
    var endDate: String
    var records: Int
    var workouts: Int
    var outcome: Outcome
}

struct StoredReceipt: Codable, Equatable, Sendable {
    var receipt: Receipt
    var at: Date
}

/// Reads Apple Health and moves packages to the computer while the app is open. Every step awaits, so the tabs
/// (the panel included) stay usable while it works.
@MainActor
@Observable
final class SyncEngine {
    enum Activity: Equatable, Sendable {
        case checking
        case reading
        case sending
        case catchingUp(Int, Int)
    }

    static let kind = "health"

    private(set) var activity: Activity?
    private(set) var lastRead: ReadSummary?
    private(set) var lastReceipt: StoredReceipt?
    private(set) var waiting: [OutboxEntry] = []
    private(set) var computer: ServerStatus?
    private(set) var computerCheckedAt: Date?
    private(set) var notice: String?
    private(set) var healthAccess: HealthReader.Access = .notAsked

    private let connection: Connection
    private let updates: UpdateCenter
    private let reader = HealthReader()
    private let outbox: Outbox
    private let defaults: UserDefaults
    private var autoTask: Task<Void, Never>?

    private enum Key {
        static let fingerprint = "sync.lastFingerprint"
        static let lastRead = "sync.lastRead"
        static let lastReceipt = "sync.lastReceipt"
    }

    init(connection: Connection, updates: UpdateCenter, outbox: Outbox = .standard(), defaults: UserDefaults = .standard) {
        self.connection = connection
        self.updates = updates
        self.outbox = outbox
        self.defaults = defaults
        lastRead = load(Key.lastRead)
        lastReceipt = load(Key.lastReceipt)
    }

    var isBusy: Bool { activity != nil }

    // MARK: Triggers

    /// About a second after the app comes to the front, read the last 3 days.
    func becameActive() {
        autoTask?.cancel()
        autoTask = Task {
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled else { return }
            await refreshWaiting()
            healthAccess = await reader.access()
            guard connection.isPaired, healthAccess == .asked else { return }
            await syncRecent(manual: false)
        }
    }

    func syncNow() async {
        await syncRecent(manual: true)
    }

    func requestHealthAccess() async {
        if HealthReader.isAvailable {
            try? await reader.requestAccess()
        }
        healthAccess = await reader.access()
    }

    func refreshWaiting() async {
        waiting = await outbox.entries()
    }

    // MARK: Reading and sending

    private func syncRecent(manual: Bool) async {
        guard activity == nil else { return }
        guard let client = connection.client() else {
            if manual { notice = ServerError.notPaired.localizedDescription }
            return
        }
        guard await healthReady(manual: manual) else { return }
        guard let window = CaptureWindow.recent(now: Date()) else { return }
        activity = .checking
        defer { activity = nil }
        notice = nil
        let courier = Courier(outbox: outbox, transport: client)
        _ = await sendWindow(window, courier: courier, useFingerprint: true)
        await refreshWaiting()
        await refreshComputer(client)
    }

    /// "Catch up 14 days": packages of up to 4 days, oldest first, each delivered before the next is made.
    func catchUp() async {
        guard activity == nil else { return }
        guard let client = connection.client() else {
            notice = ServerError.notPaired.localizedDescription
            return
        }
        guard await healthReady(manual: true) else { return }
        let windows = CaptureWindow.catchUp(now: Date())
        defer { activity = nil }
        notice = nil
        let courier = Courier(outbox: outbox, transport: client)
        for (index, window) in windows.enumerated() {
            activity = .catchingUp(index + 1, windows.count)
            if !(await sendWindow(window, courier: courier, useFingerprint: false)) {
                break
            }
        }
        await refreshWaiting()
        await refreshComputer(client)
    }

    /// Returns false when something is left waiting, so a catch-up stops instead of piling up packages.
    private func sendWindow(_ window: CaptureWindow, courier: Courier, useFingerprint: Bool) async -> Bool {
        guard await settleWaiting(courier) else {
            notice = String(localized: "A package is still waiting for your computer. Check it below before sending more.")
            return false
        }
        if case .catchingUp = activity {} else { activity = .reading }
        let result: HealthReader.Result
        do {
            result = try await reader.read(window)
        } catch {
            record(window, records: 0, workouts: 0, outcome: .failed)
            notice = String(localized: "Apple Health could not be read: \(error.localizedDescription)")
            return false
        }
        let records = result.records, workouts = result.workouts
        if records.isEmpty && workouts.isEmpty {
            record(window, records: 0, workouts: 0, outcome: .empty)
            return true
        }
        let fingerprint = await Task.detached(priority: .userInitiated) {
            Fingerprint.of(records: records, workouts: workouts)
        }.value
        if useFingerprint, fingerprint == defaults.string(forKey: Key.fingerprint) {
            record(window, records: records.count, workouts: workouts.count, outcome: .nothingNew)
            return true
        }
        let package = makePackage(window, records: records, workouts: workouts, completedAt: result.completedAt)
        return await freezeAndDeliver(package, courier: courier, fingerprint: fingerprint, window: window)
    }

    private func freezeAndDeliver(_ package: CapturePackage, courier: Courier, fingerprint: String?,
                                  window: CaptureWindow?) async -> Bool {
        let entry: OutboxEntry
        do {
            entry = try await outbox.freeze(package)
        } catch {
            notice = String(localized: "The package could not be saved on the phone: \(error.localizedDescription)")
            return false
        }
        if let fingerprint { defaults.set(fingerprint, forKey: Key.fingerprint) }
        if let window {
            record(window, records: package.records.count, workouts: package.workouts.count, outcome: .sent)
        }
        if case .catchingUp = activity {} else { activity = .sending }
        return handle(await courier.deliver(entry.id))
    }

    /// Asks about a package that is already waiting. Never resends on its own.
    private func settleWaiting(_ courier: Courier) async -> Bool {
        guard let entry = await outbox.waiting(kind: SyncEngine.kind) else { return true }
        return handle(await courier.reconcile(entry.id, userTapped: false))
    }

    @discardableResult
    private func handle(_ outcome: Courier.Outcome) -> Bool {
        switch outcome {
        case .cleared(let receipt):
            lastReceipt = StoredReceipt(receipt: receipt, at: Date())
            save(lastReceipt, Key.lastReceipt)
            return true
        case .kept(let entry):
            notice = Strings.state(entry.state)
            return false
        case .missing:
            return true
        }
    }

    private func healthReady(manual: Bool) async -> Bool {
        healthAccess = await reader.access()
        switch healthAccess {
        case .unavailable:
            if manual { notice = String(localized: "Apple Health is not available on this device.") }
            return false
        case .notAsked:
            guard manual else { return false }
            await requestHealthAccess()
            return healthAccess == .asked
        case .asked:
            return true
        }
    }

    private func makePackage(_ window: CaptureWindow, records: [HealthRecord], workouts: [WorkoutRecord],
                             completedAt: Date) -> CapturePackage {
        let formats = DateFormats(timeZone: window.timeZone)
        return CapturePackage(
            schema: CapturePackage.schemaName, packageID: CapturePackage.newID(), kind: SyncEngine.kind,
            createdAt: formats.isoString(Date()), timezone: window.timeZone.identifier,
            device: PackageDevice(id: connection.installID, name: connection.deviceName,
                                  appVersion: "\(UpdateCenter.appVersion) (\(UpdateCenter.appBuild))"),
            window: window.packageWindow(readCompletedAt: completedAt),
            records: records, workouts: workouts)
    }

    private func record(_ window: CaptureWindow, records: Int, workouts: Int, outcome: ReadSummary.Outcome) {
        lastRead = ReadSummary(at: Date(), startDate: window.startDate, endDate: window.endDate,
                               records: records, workouts: workouts, outcome: outcome)
        save(lastRead, Key.lastRead)
    }

    // MARK: The outbox, by hand

    /// "Check and retry": ask the computer, and send the same bytes again only if it has never seen them.
    func checkAndRetry(_ id: String) async {
        guard activity == nil, let client = connection.client() else {
            if !connection.isPaired { notice = ServerError.notPaired.localizedDescription }
            return
        }
        activity = .checking
        defer { activity = nil }
        notice = nil
        handle(await Courier(outbox: outbox, transport: client).reconcile(id, userTapped: true))
        await refreshWaiting()
        await refreshComputer(client)
    }

    /// "Discard this package": the next read is sent again even if it matches the discarded one.
    func discard(_ id: String) async {
        await outbox.remove(id)
        defaults.removeObject(forKey: Key.fingerprint)
        notice = nil
        await refreshWaiting()
    }

    // MARK: The computer

    func refreshComputer() async {
        guard let client = connection.client() else { return }
        await refreshComputer(client)
    }

    private func refreshComputer(_ client: ServerClient) async {
        guard let status = try? await client.status() else { return }
        computer = status
        computerCheckedAt = Date()
        connection.rememberServerVersion(status.version)
        updates.note(status: status)
    }

    // MARK: Storage

    private func load<T: Decodable>(_ key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private func save<T: Encodable>(_ value: T?, _ key: String) {
        guard let value, let data = try? JSONEncoder().encode(value) else { return }
        defaults.set(data, forKey: key)
    }

    #if DEBUG
    /// Posts a made-up 3-day package through the real outbox, for checks without Apple Health.
    func sendSample() async {
        // The automatic read may be running; wait for it rather than skipping the sample.
        for _ in 0..<150 where activity != nil {
            try? await Task.sleep(for: .milliseconds(200))
        }
        guard activity == nil, let client = connection.client() else {
            notice = ServerError.notPaired.localizedDescription
            return
        }
        activity = .sending
        defer { activity = nil }
        notice = nil
        let courier = Courier(outbox: outbox, transport: client)
        guard await settleWaiting(courier) else { return }
        let package = SamplePackage.make(now: Date(), deviceID: connection.installID,
                                         appVersion: "\(UpdateCenter.appVersion) (\(UpdateCenter.appBuild))")
        _ = await freezeAndDeliver(package, courier: courier, fingerprint: nil, window: nil)
        await refreshWaiting()
        await refreshComputer(client)
    }
    #endif
}
