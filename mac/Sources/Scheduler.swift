import AppKit

/// Decides when to collect, check for updates and read the status. It looks at the clock every 10 seconds
/// instead of setting one long timer per job, so a Mac that slept through a due time catches up on waking.
final class Scheduler: NSObject {
    var onCollect: (() -> Void)?
    var onUpdateCheck: (() -> Void)?
    var onStatus: (() -> Void)?
    var onTick: (() -> Void)?

    private(set) var nextCollect: Date
    private var nextUpdateCheck: Date
    private var nextStatus: Date
    private var timer: Timer?

    static let statusEvery: TimeInterval = 300
    static let updateEvery: TimeInterval = 86400

    /// `quick` (HEALTHAIO_MAC_QUICKSTART=1) shortens the first waits for tests.
    init(quick: Bool) {
        let now = Date()
        nextCollect = now.addingTimeInterval(quick ? 3 : 30)
        nextUpdateCheck = now.addingTimeInterval(quick ? 6 : 60)
        nextStatus = now.addingTimeInterval(Self.statusEvery)
        super.init()
    }

    var collectInterval: TimeInterval { TimeInterval(AppSettings.shared.collectEveryHours) * 3600 }

    func start() {
        let timer = Timer(timeInterval: 10, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        timer.tolerance = 2
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(tick),
                                                          name: NSWorkspace.didWakeNotification, object: nil)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
        NSWorkspace.shared.notificationCenter.removeObserver(self)
    }

    /// A collection started (by the schedule or by hand): the next one is a full interval away.
    func collectStarted() {
        nextCollect = Date().addingTimeInterval(collectInterval)
    }

    func intervalChanged() {
        nextCollect = min(nextCollect, Date().addingTimeInterval(collectInterval))
    }

    func statusRead() {
        nextStatus = Date().addingTimeInterval(Self.statusEvery)
    }

    @objc func tick() {
        let now = Date()
        onTick?()
        if now >= nextCollect {
            nextCollect = now.addingTimeInterval(collectInterval)
            onCollect?()
        }
        if now >= nextUpdateCheck && AppSettings.shared.autoUpdateCheck {
            nextUpdateCheck = now.addingTimeInterval(Self.updateEvery)
            onUpdateCheck?()
        }
        if now >= nextStatus {
            nextStatus = now.addingTimeInterval(Self.statusEvery)
            onStatus?()
        }
    }
}
