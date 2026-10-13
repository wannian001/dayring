import Foundation

/// Where a frozen package stands. Only a `projected` receipt removes it from the outbox.
enum PackageState: String, Codable, Sendable {
    /// Frozen, not yet answered (or the computer did not accept the token, so it was not stored).
    case waiting
    /// Sent, but the answer never came or could not be read: ask the computer before doing anything else.
    case unknown
    /// Stored on the computer, not yet in the tables.
    case landed
    /// Stored, but the rows could not be written; the computer tries again on its next start.
    case failed
    /// The computer has never seen it; the same bytes may be sent again when the user taps.
    case notFound
    /// The computer refused it for good (invalid package, or another package already has this id).
    case refused
}

struct OutboxEntry: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var kind: String
    var frozenAt: Date
    var startDate: String
    var endDate: String
    var byteCount: Int
    var state: PackageState
    var message: String?
    var lastTriedAt: Date?
}

/// Packages waiting for the computer. Each one is frozen (its id and exact bytes) before it is first posted, in
/// Application Support, excluded from backups. Only one package per kind may wait at a time.
actor Outbox {
    let directory: URL

    init(directory: URL) {
        self.directory = directory
    }

    static func standard() -> Outbox {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        return Outbox(directory: base.appending(path: "Outbox", directoryHint: .isDirectory))
    }

    private func prepare() throws {
        var url = directory
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try url.setResourceValues(values)
    }

    private func bytesURL(_ id: String) -> URL { directory.appending(path: "\(id).json") }
    private func metaURL(_ id: String) -> URL { directory.appending(path: "\(id).meta") }

    enum FreezeError: Error { case alreadyWaiting, alreadyFrozen, badID }

    /// Freezes a package: these bytes, under this id, are what will be sent every time.
    func freeze(_ package: CapturePackage) throws -> OutboxEntry {
        guard CapturePackage.isValidID(package.packageID) else { throw FreezeError.badID }
        guard waiting(kind: package.kind) == nil else { throw FreezeError.alreadyWaiting }
        try prepare()
        let bytes = try package.encoded()
        let entry = OutboxEntry(id: package.packageID, kind: package.kind, frozenAt: Date(),
                                startDate: package.window.startDate, endDate: package.window.endDate,
                                byteCount: bytes.count, state: .waiting)
        // A frozen package is never rewritten. (Foundation cannot combine .atomic with .withoutOverwriting.)
        guard !FileManager.default.fileExists(atPath: bytesURL(entry.id).path()) else { throw FreezeError.alreadyFrozen }
        try bytes.write(to: bytesURL(entry.id), options: .atomic)
        try save(entry)
        return entry
    }

    func entries() -> [OutboxEntry] {
        guard let names = try? FileManager.default.contentsOfDirectory(atPath: directory.path()) else { return [] }
        return names.filter { $0.hasSuffix(".meta") }
            .compactMap { name in
                guard let data = try? Data(contentsOf: directory.appending(path: name)) else { return nil }
                return try? JSONDecoder().decode(OutboxEntry.self, from: data)
            }
            .sorted { $0.frozenAt < $1.frozenAt }
    }

    func entry(_ id: String) -> OutboxEntry? {
        guard let data = try? Data(contentsOf: metaURL(id)) else { return nil }
        return try? JSONDecoder().decode(OutboxEntry.self, from: data)
    }

    func waiting(kind: String) -> OutboxEntry? {
        entries().first { $0.kind == kind }
    }

    func bytes(_ id: String) throws -> Data {
        try Data(contentsOf: bytesURL(id))
    }

    func save(_ entry: OutboxEntry) throws {
        try prepare()
        try JSONEncoder().encode(entry).write(to: metaURL(entry.id), options: .atomic)
    }

    func remove(_ id: String) {
        try? FileManager.default.removeItem(at: metaURL(id))
        try? FileManager.default.removeItem(at: bytesURL(id))
    }
}
