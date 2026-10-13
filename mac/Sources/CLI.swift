import Darwin
import Foundation

enum Timeouts {
    static let short: TimeInterval = 30
    static let collect: TimeInterval = 600
    static let update: TimeInterval = 600
    static let renew: TimeInterval = 1200
}

/// Why a command could not even start.
enum CLIProblem: Error {
    case noConfig
    case configMissing(String)
    case noPython(String)
    case noExecutable(String)

    var message: String {
        switch self {
        case .noConfig: return S.noConfig
        case .configMissing(let path): return S.configMissing((path as NSString).abbreviatingWithTildeInPath)
        case .noPython(let path): return S.noPython(path)
        case .noExecutable(let name): return S.noExecutable(name)
        }
    }
}

struct CLIResult: Sendable {
    var exitCode: Int32 = -1
    var stdout = Data()
    var stderr = Data()
    var timedOut = false
    /// Set when the command could not start at all.
    var problem: String?

    var json: JSONObject? { JSONParse.object(from: stdout) }

    /// The last few lines of stderr, which is where Python puts a traceback.
    var stderrTail: String { Self.tail(stderr) }

    /// A sentence for the UI when the command printed no JSON.
    var failureText: String {
        if let problem { return problem }
        if timedOut { return S.timedOut }
        var text = S.noAnswer(exitCode)
        let tail = stderrTail.isEmpty ? Self.tail(stdout) : stderrTail
        if !tail.isEmpty { text += "\n" + tail }
        return text
    }

    private static func tail(_ data: Data) -> String {
        let lines = String(decoding: data, as: UTF8.self).split(whereSeparator: \.isNewline)
        let text = lines.suffix(6).joined(separator: "\n")
        return text.count > 700 ? "…" + String(text.suffix(700)) : text
    }
}

/// One way to run healthaio: `<python> -m healthaio --config <toml> <command…>` with PYTHONPATH set to the repository
/// and the config's folder as the working directory. HEALTHAIO_CLI replaces `<python> -m healthaio` with any command
/// (the tests point it at mac/tools/fake_healthaio.py).
struct CLICommand: Sendable {
    let executable: String
    let arguments: [String]
    let environment: [String: String]
    let directory: URL
}

final class CLI: @unchecked Sendable {
    static let shared = CLI()

    private let lock = NSLock()
    private var running: [pid_t: Process] = [:]

    func command(_ args: [String]) -> Result<CLICommand, CLIProblem> {
        let settings = AppSettings.shared
        let fm = FileManager.default
        var environment = ProcessInfo.processInfo.environment

        var prefix: [String]
        if let custom = environment["HEALTHAIO_CLI"], !custom.trimmingCharacters(in: .whitespaces).isEmpty {
            prefix = ShellWords.split(custom)
        } else {
            let python = settings.pythonPath
            guard fm.isExecutableFile(atPath: python) else { return .failure(.noPython(python)) }
            prefix = [python, "-m", "healthaio"]
        }

        guard let config = settings.configPath else { return .failure(.noConfig) }
        guard fm.fileExists(atPath: config) else { return .failure(.configMissing(config)) }

        // An app started from Finder gets a bare PATH; the CLI needs git, xcrun and the Python's own folder.
        var path = (environment["PATH"] ?? "").split(separator: ":").map(String.init)
        if let first = prefix.first, first.contains("/") {
            let folder = (first as NSString).deletingLastPathComponent
            if !path.contains(folder) { path.insert(folder, at: 0) }
        }
        for dir in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"] where !path.contains(dir) {
            path.append(dir)
        }
        environment["PATH"] = path.joined(separator: ":")
        if let repo = AppSettings.repoPath {
            let existing = environment["PYTHONPATH"].map { ":" + $0 } ?? ""
            environment["PYTHONPATH"] = repo + existing
        }
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        environment.removeValue(forKey: "HEALTHAIO_CLI")

        guard let name = prefix.first, let executable = Self.resolve(name, path: path) else {
            return .failure(.noExecutable(prefix.first ?? "?"))
        }
        let directory = URL(fileURLWithPath: config).deletingLastPathComponent()
        return .success(CLICommand(executable: executable,
                                   arguments: Array(prefix.dropFirst()) + ["--config", config] + args,
                                   environment: environment,
                                   directory: directory))
    }

    /// Runs a command off the main thread and calls back on the main thread. Past `timeout` the command and
    /// everything it started are stopped.
    func run(_ args: [String], timeout: TimeInterval, completion: @escaping (CLIResult) -> Void) {
        let label = args.joined(separator: " ")
        let command: CLICommand
        switch self.command(args) {
        case .failure(let problem):
            let result = CLIResult(problem: problem.message)
            DispatchQueue.main.async { completion(result) }
            return
        case .success(let c):
            command = c
        }
        AppLog.info("run: \(label)")
        DispatchQueue.global(qos: .userInitiated).async {
            let result = self.runBlocking(command, timeout: timeout)
            AppLog.info("done: \(label): exit \(result.exitCode)\(result.timedOut ? ", timed out" : "")\(result.problem.map { ", \($0)" } ?? "")")
            DispatchQueue.main.async { completion(result) }
        }
    }

    /// Stops every command still running (when the app quits).
    func terminateAll() {
        lock.lock()
        let processes = Array(running.values)
        lock.unlock()
        for p in processes where p.isRunning { ProcessTree.terminate(p.processIdentifier, grace: 2) }
    }

    var isIdle: Bool {
        lock.lock()
        defer { lock.unlock() }
        return running.isEmpty
    }

    private func runBlocking(_ command: CLICommand, timeout: TimeInterval) -> CLIResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command.executable)
        process.arguments = command.arguments
        process.environment = command.environment
        process.currentDirectoryURL = command.directory
        process.standardInput = FileHandle.nullDevice
        let out = Pipe(), err = Pipe()
        process.standardOutput = out
        process.standardError = err
        let collector = OutputCollector()
        collector.attach(out, isError: false)
        collector.attach(err, isError: true)
        let exited = DispatchSemaphore(value: 0)
        process.terminationHandler = { _ in exited.signal() }

        do {
            try process.run()
        } catch {
            collector.detach([out, err])
            return CLIResult(problem: S.cannotStart(error.localizedDescription))
        }
        let pid = process.processIdentifier
        lock.lock(); running[pid] = process; lock.unlock()

        var timedOut = false
        if exited.wait(timeout: .now() + timeout) == .timedOut {
            timedOut = true
            ProcessTree.terminate(pid, grace: 3)
            _ = exited.wait(timeout: .now() + 5)
        }
        lock.lock(); running[pid] = nil; lock.unlock()

        // A grandchild that kept the pipes open must not hold the answer back for long.
        collector.waitClosed(timeout: 2)
        collector.detach([out, err])
        let (stdout, stderr) = collector.contents()
        return CLIResult(exitCode: process.isRunning ? -1 : process.terminationStatus,
                         stdout: stdout, stderr: stderr, timedOut: timedOut, problem: nil)
    }

    static func resolve(_ name: String, path: [String]) -> String? {
        let fm = FileManager.default
        if name.contains("/") { return fm.isExecutableFile(atPath: name) ? name : nil }
        for dir in path {
            let candidate = (dir as NSString).appendingPathComponent(name)
            if fm.isExecutableFile(atPath: candidate) { return candidate }
        }
        return nil
    }
}

/// Reads a child's stdout and stderr as they come, so a full pipe never blocks it.
private final class OutputCollector: @unchecked Sendable {
    private let condition = NSCondition()
    private var out = Data()
    private var err = Data()
    private var closed: Set<Bool> = []
    private let limit = 8 * 1024 * 1024

    func attach(_ pipe: Pipe, isError: Bool) {
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self else { return }
            self.condition.lock()
            if data.isEmpty {
                handle.readabilityHandler = nil
                self.closed.insert(isError)
                self.condition.broadcast()
            } else if isError {
                self.err.append(data)
                if self.err.count > 65536 { self.err = self.err.suffix(65536) }
            } else if self.out.count < self.limit {
                self.out.append(data)
            }
            self.condition.unlock()
        }
    }

    func waitClosed(timeout: TimeInterval) {
        let deadline = Date().addingTimeInterval(timeout)
        condition.lock()
        while closed.count < 2 {
            if !condition.wait(until: deadline) { break }
        }
        condition.unlock()
    }

    func detach(_ pipes: [Pipe]) {
        for pipe in pipes { pipe.fileHandleForReading.readabilityHandler = nil }
    }

    func contents() -> (Data, Data) {
        condition.lock()
        defer { condition.unlock() }
        return (out, err)
    }
}

/// Stops a process together with everything it started (a renew runs xcodebuild, an update runs git).
enum ProcessTree {
    static func children(of pid: pid_t) -> [pid_t] {
        var buffer = [pid_t](repeating: 0, count: 512)
        let count = buffer.withUnsafeMutableBytes { raw in
            proc_listchildpids(pid, raw.baseAddress, Int32(raw.count))
        }
        guard count > 0 else { return [] }
        return buffer.prefix(min(Int(count), buffer.count)).filter { $0 > 0 }
    }

    static func descendants(of pid: pid_t) -> [pid_t] {
        var found: [pid_t] = []
        var queue = [pid]
        while let next = queue.popLast(), found.count < 1000 {
            let kids = children(of: next)
            found.append(contentsOf: kids)
            queue.append(contentsOf: kids)
        }
        return found
    }

    /// SIGTERM to the whole tree, then SIGKILL to whatever is still there after `grace` seconds.
    static func terminate(_ pid: pid_t, grace: TimeInterval) {
        guard pid > 0 else { return }
        let all = [pid] + descendants(of: pid)
        for p in all { kill(p, SIGTERM) }
        let deadline = Date().addingTimeInterval(grace)
        while Date() < deadline {
            if !all.contains(where: alive) { return }
            usleep(50_000)
        }
        for p in all where alive(p) { kill(p, SIGKILL) }
    }

    static func alive(_ pid: pid_t) -> Bool { kill(pid, 0) == 0 }
}

/// Splits HEALTHAIO_CLI the way a shell would split simple words, quotes included.
enum ShellWords {
    static func split(_ text: String) -> [String] {
        var words: [String] = []
        var current = ""
        var inWord = false
        var quote: Character?
        var escaped = false
        for ch in text {
            if escaped { current.append(ch); escaped = false; continue }
            if ch == "\\" && quote != "'" { escaped = true; inWord = true; continue }
            if let q = quote {
                if ch == q { quote = nil } else { current.append(ch) }
                continue
            }
            if ch == "\"" || ch == "'" { quote = ch; inWord = true; continue }
            if ch == " " || ch == "\t" {
                if inWord { words.append(current); current = ""; inWord = false }
                continue
            }
            current.append(ch)
            inWord = true
        }
        if inWord { words.append(current) }
        return words
    }
}
