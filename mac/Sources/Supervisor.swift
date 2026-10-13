import Foundation

/// Keeps `healthaio serve` running as a child of this app. As a child it shares the app's Full Disk Access (macOS
/// counts a child's file access against the app that started it) and it stops when the app quits.
/// An unexpected exit is retried after a growing pause (2 s, 4 s, … at most 5 min); a server that stayed up for a
/// minute starts the count again.
final class ServerSupervisor: NSObject {
    enum State: Equatable {
        case stopped
        /// No config or no Python: nothing to start until the settings change.
        case blocked(String)
        case starting
        case running
        /// The port answers, but not from our child: another `healthaio serve` holds it.
        case external
        case retrying(at: Date, lastLine: String)
    }

    var onChange: (() -> Void)?
    private(set) var state: State = .stopped {
        didSet { if state != oldValue { onChange?() } }
    }
    private(set) var lan = false
    private(set) var port = AppSettings.defaultPort

    private let log = RotatingLog(name: "server.log", maxBytes: 5_000_000)
    private let tail = LineTail(limit: 20)
    private var process: Process?
    private var generation = 0
    private var wanted = false
    private var failures = 0
    private var startedAt = Date.distantPast
    private var retryTimer: Timer?
    private var probeTimer: Timer?
    private var fastProbes = 0

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 2
        config.timeoutIntervalForResource = 3
        config.connectionProxyDictionary = ["HTTPEnable": 0, "HTTPSEnable": 0]
        return URLSession(configuration: config)
    }()

    var lastOutput: String { tail.last }

    func start(lan: Bool, port: Int) {
        self.lan = lan
        self.port = port
        wanted = true
        failures = 0
        stopChild()
        launch()
    }

    func stop() {
        wanted = false
        retryTimer?.invalidate()
        retryTimer = nil
        probeTimer?.invalidate()
        probeTimer = nil
        stopChild()
        state = .stopped
        log.flush()
    }

    private func stopChild() {
        guard let p = process else { return }
        process = nil
        generation += 1 // its exit is expected now
        if p.isRunning { ProcessTree.terminate(p.processIdentifier, grace: 3) }
        log.line("stopped pid \(p.processIdentifier)")
        AppLog.info("server stopped (pid \(p.processIdentifier))")
    }

    private func launch() {
        retryTimer?.invalidate()
        retryTimer = nil
        guard wanted else { return }
        var args = ["serve"]
        if lan { args.append("--lan") }
        args += ["--port", String(port)]
        let command: CLICommand
        switch CLI.shared.command(args) {
        case .failure(let problem):
            state = .blocked(problem.message)
            return
        case .success(let c):
            command = c
        }

        let p = Process()
        p.executableURL = URL(fileURLWithPath: command.executable)
        p.arguments = command.arguments
        p.environment = command.environment
        p.currentDirectoryURL = command.directory
        p.standardInput = FileHandle.nullDevice
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        let log = self.log, tail = self.tail
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
                return
            }
            log.append(data)
            tail.add(data)
        }
        generation += 1
        let gen = generation
        p.terminationHandler = { [weak self] proc in
            let status = proc.terminationStatus
            DispatchQueue.main.async { self?.childExited(generation: gen, status: status) }
        }

        log.line("start: \(args.joined(separator: " "))")
        do {
            try p.run()
        } catch {
            pipe.fileHandleForReading.readabilityHandler = nil
            log.line("could not start: \(error.localizedDescription)")
            tail.addLine(error.localizedDescription)
            failures += 1
            scheduleRetry()
            return
        }
        process = p
        startedAt = Date()
        state = .starting
        log.line("pid \(p.processIdentifier)")
        AppLog.info("server started: \(args.joined(separator: " ")) (pid \(p.processIdentifier))")
        startProbing(fast: true)
    }

    private func childExited(generation gen: Int, status: Int32) {
        guard gen == generation else { return }
        process = nil
        log.line("exited with status \(status)")
        AppLog.info("server exited with status \(status)")
        guard wanted else {
            state = .stopped
            return
        }
        if Date().timeIntervalSince(startedAt) > 60 { failures = 0 }
        failures += 1
        // Another server may hold the port: one started by hand, or one that restarted itself after an update
        // from the web page. Then there is nothing to restart, only to watch.
        probe { [weak self] answered in
            guard let self, self.wanted, self.process == nil else { return }
            if answered {
                AppLog.info("port \(self.port) answers from another process")
                self.state = .external
                self.startProbing(fast: false)
            } else {
                self.scheduleRetry()
            }
        }
    }

    private func scheduleRetry() {
        let delay = min(300, 2 * pow(2, Double(max(0, failures - 1))))
        state = .retrying(at: Date().addingTimeInterval(delay), lastLine: tail.last)
        let timer = Timer(timeInterval: delay, target: self, selector: #selector(retryFired), userInfo: nil, repeats: false)
        RunLoop.main.add(timer, forMode: .common)
        retryTimer = timer
    }

    @objc private func retryFired() {
        launch()
    }

    private func startProbing(fast: Bool) {
        probeTimer?.invalidate()
        fastProbes = fast ? 30 : 0
        let timer = Timer(timeInterval: fast ? 1 : 30, target: self, selector: #selector(probeFired), userInfo: nil, repeats: true)
        RunLoop.main.add(timer, forMode: .common)
        probeTimer = timer
    }

    @objc private func probeFired() {
        probe { [weak self] answered in self?.probed(answered) }
    }

    private func probed(_ answered: Bool) {
        if process != nil {
            if answered && state != .running {
                state = .running
                log.line("answering on port \(port)")
            }
            if fastProbes > 0 {
                fastProbes -= 1
                if answered || fastProbes == 0 { startProbing(fast: false) }
            }
        } else if state == .external && !answered {
            AppLog.info("the other server on port \(port) stopped; starting ours")
            failures = 0
            launch()
        }
    }

    /// Any HTTP answer on the port counts: the server is up.
    private func probe(_ done: @escaping (Bool) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:\(port)/capture/v1/hello") else {
            done(false)
            return
        }
        session.dataTask(with: url) { _, response, _ in
            let answered = response is HTTPURLResponse
            DispatchQueue.main.async { done(answered) }
        }.resume()
    }
}
