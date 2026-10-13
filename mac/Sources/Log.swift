import Foundation

enum Paths {
    static var home: URL { FileManager.default.homeDirectoryForCurrentUser }

    /// ~/Library/Logs/HealthAIO, or HEALTHAIO_LOG_DIR (tests keep their logs out of the user's Library).
    static var logs: URL {
        if let dir = ProcessInfo.processInfo.environment["HEALTHAIO_LOG_DIR"], !dir.isEmpty {
            return URL(fileURLWithPath: dir, isDirectory: true)
        }
        return home.appendingPathComponent("Library/Logs/HealthAIO", isDirectory: true)
    }
}

/// An append-only log file. Past `maxBytes` it is moved to `<name>.1` (replacing the older one), so the two
/// files together never grow beyond twice that.
final class RotatingLog: @unchecked Sendable {
    let url: URL
    private let maxBytes: UInt64
    private let queue: DispatchQueue
    private var handle: FileHandle?
    private var size: UInt64 = 0

    init(name: String, maxBytes: UInt64) {
        url = Paths.logs.appendingPathComponent(name)
        self.maxBytes = maxBytes
        queue = DispatchQueue(label: "healthaio.log.\(name)")
    }

    func append(_ data: Data) {
        queue.async { self.write(data) }
    }

    func line(_ text: String) {
        append(Data("\(Self.stamp()) \(text)\n".utf8))
    }

    /// Waits until everything written so far is on disk (used when quitting).
    func flush() {
        queue.sync { try? handle?.synchronize() }
    }

    private func write(_ data: Data) {
        if handle == nil { open() }
        guard let handle else { return }
        do {
            try handle.write(contentsOf: data)
            size += UInt64(data.count)
        } catch {
            self.handle = nil
            return
        }
        if size > maxBytes { rotate() }
    }

    private func open() {
        let fm = FileManager.default
        try? fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !fm.fileExists(atPath: url.path) { fm.createFile(atPath: url.path, contents: nil) }
        handle = try? FileHandle(forWritingTo: url)
        size = (try? handle?.seekToEnd()) ?? 0
    }

    private func rotate() {
        try? handle?.close()
        handle = nil
        let older = url.appendingPathExtension("1")
        try? FileManager.default.removeItem(at: older)
        try? FileManager.default.moveItem(at: url, to: older)
        size = 0
    }

    private static let stampFormat: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f
    }()

    static func stamp() -> String { stampFormat.string(from: Date()) }
}

/// What the app did and when (commands run, their exit codes, server starts and stops). Never any health data.
enum AppLog {
    static let file = RotatingLog(name: "app.log", maxBytes: 1_000_000)
    static func info(_ text: String) { file.line(text) }
}

/// The last lines a child process printed, to show why it stopped.
final class LineTail: @unchecked Sendable {
    private let lock = NSLock()
    private let limit: Int
    private var lines: [String] = []
    private var partial = ""

    init(limit: Int) { self.limit = limit }

    func add(_ data: Data) {
        let text = String(decoding: data, as: UTF8.self)
        lock.lock()
        defer { lock.unlock() }
        var parts = (partial + text).components(separatedBy: "\n")
        partial = parts.removeLast()
        lines.append(contentsOf: parts.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty })
        if lines.count > limit { lines.removeFirst(lines.count - limit) }
    }

    func addLine(_ line: String) { add(Data((line + "\n").utf8)) }

    var last: String {
        lock.lock()
        defer { lock.unlock() }
        let line = lines.last ?? partial.trimmingCharacters(in: .whitespaces)
        return line.count > 200 ? String(line.prefix(200)) + "…" : line
    }
}
