import XCTest
@testable import HealthAIO

/// A computer that answers from a script and records what it was sent.
private actor FakeComputer: CaptureTransport {
    var postAnswers: [TransportResult]
    var lookupAnswers: [TransportResult]
    private(set) var posted: [Data] = []
    private(set) var lookups: [String] = []

    init(post: [TransportResult] = [], lookup: [TransportResult] = []) {
        postAnswers = post
        lookupAnswers = lookup
    }

    func postPackage(_ bytes: Data) async -> TransportResult {
        posted.append(bytes)
        return postAnswers.isEmpty ? .failure("no script") : postAnswers.removeFirst()
    }

    func lookupPackage(_ id: String) async -> TransportResult {
        lookups.append(id)
        return lookupAnswers.isEmpty ? .failure("no script") : lookupAnswers.removeFirst()
    }
}

final class OutboxTests: XCTestCase {
    private var directory: URL!

    override func setUp() {
        directory = FileManager.default.temporaryDirectory.appending(path: "outbox-\(UUID().uuidString)")
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: directory)
    }

    private func package() throws -> CapturePackage {
        try JSONDecoder().decode(CapturePackage.self, from: Fixture.data())
    }

    private func receipt(_ id: String, _ status: String, ok: Bool = true) -> TransportResult {
        let json = """
        {"ok": \(ok), "package_id": "\(id)", "status": "\(status)", "landed_at": "2026-10-13T21:05:12+11:00",
         "rows": {"body_daily": 3, "workouts": 1, "meals": 0},
         "window": {"start_date": "2026-10-11", "end_date": "2026-10-13"}}
        """
        return .answer(status: 200, body: Data(json.utf8))
    }

    // MARK: Policy

    func testProjectedClears() throws {
        let id = try package().packageID
        guard case .clear(let r) = OutboxPolicy.afterPost(id: id, result: receipt(id, "projected")) else {
            return XCTFail("projected should clear")
        }
        XCTAssertEqual(r.rows?["body_daily"], 3)
    }

    func testOnlyAMatchingProjectedReceiptClears() throws {
        let id = try package().packageID
        XCTAssertEqual(OutboxPolicy.afterPost(id: id, result: receipt("ios-other", "projected")), .keep(.unknown, nil))
        XCTAssertEqual(OutboxPolicy.afterPost(id: id, result: receipt(id, "projected", ok: false)), .keep(.unknown, nil))
        XCTAssertEqual(OutboxPolicy.afterPost(id: id, result: receipt(id, "landed")), .keep(.landed, nil))
        XCTAssertEqual(OutboxPolicy.afterPost(id: id, result: .answer(status: 200, body: Data("<html>".utf8))),
                       .keep(.unknown, nil))
    }

    func testTimeoutAnd5xxAreUnknown() {
        XCTAssertEqual(OutboxPolicy.afterPost(id: "ios-a", result: .failure("timed out")), .keep(.unknown, nil))
        XCTAssertEqual(OutboxPolicy.afterPost(id: "ios-a", result: .answer(status: 502, body: Data())),
                       .keep(.unknown, nil))
    }

    func testConflictAndBadPackageAreRefused() {
        let conflict = OutboxPolicy.afterPost(
            id: "ios-a", result: .answer(status: 409, body: Data(#"{"error":"same id, other content"}"#.utf8)))
        XCTAssertEqual(conflict, .keep(.refused, "same id, other content"))
        guard case .keep(.refused, _) = OutboxPolicy.afterPost(id: "ios-a", result: .answer(status: 400, body: Data()))
        else { return XCTFail("400 should be refused") }
    }

    func testLookupNotFound() {
        let body = Data(#"{"package_id":"ios-a","status":"not_found"}"#.utf8)
        XCTAssertEqual(OutboxPolicy.afterLookup(id: "ios-a", result: .answer(status: 200, body: body)), .notFound)
        XCTAssertEqual(OutboxPolicy.afterLookup(id: "ios-a", result: .answer(status: 404, body: body)), .notFound)
        XCTAssertEqual(OutboxPolicy.afterLookup(id: "ios-a", result: .failure("offline")), .keep(.unknown, nil))
    }

    // MARK: Outbox and courier together

    func testProjectedRemovesThePackage() async throws {
        let outbox = Outbox(directory: directory)
        let package = try package()
        let entry = try await outbox.freeze(package)
        let computer = FakeComputer(post: [receipt(package.packageID, "projected")])
        let outcome = await Courier(outbox: outbox, transport: computer).deliver(entry.id)
        guard case .cleared = outcome else { return XCTFail("expected cleared, got \(outcome)") }
        let left = await outbox.entries()
        XCTAssertTrue(left.isEmpty)
        let posted = await computer.posted
        XCTAssertEqual(posted, [try package.encoded()])
    }

    func testLandedKeepsThePackage() async throws {
        let outbox = Outbox(directory: directory)
        let package = try package()
        let entry = try await outbox.freeze(package)
        let computer = FakeComputer(post: [receipt(package.packageID, "landed")])
        let outcome = await Courier(outbox: outbox, transport: computer).deliver(entry.id)
        guard case .kept(let kept) = outcome else { return XCTFail("expected kept") }
        XCTAssertEqual(kept.state, .landed)
        let stored = await outbox.entry(entry.id)
        XCTAssertEqual(stored?.state, .landed)
    }

    /// Timeout → unknown; the next look asks first and never resends on its own; after the user taps, the same
    /// bytes go out again only because the computer says not_found.
    func testUnknownReconcilesBeforeResending() async throws {
        let outbox = Outbox(directory: directory)
        let package = try package()
        let entry = try await outbox.freeze(package)
        let frozen = try await outbox.bytes(entry.id)
        let notFound = TransportResult.answer(status: 200,
                                              body: Data(#"{"package_id":"\#(package.packageID)","status":"not_found"}"#.utf8))
        let computer = FakeComputer(post: [.failure("timed out"), receipt(package.packageID, "projected")],
                                    lookup: [notFound, notFound])
        let courier = Courier(outbox: outbox, transport: computer)

        guard case .kept(let first) = await courier.deliver(entry.id) else { return XCTFail() }
        XCTAssertEqual(first.state, .unknown)

        guard case .kept(let second) = await courier.reconcile(entry.id, userTapped: false) else { return XCTFail() }
        XCTAssertEqual(second.state, .notFound)
        var posted = await computer.posted
        XCTAssertEqual(posted.count, 1, "no resend without the user")

        guard case .cleared = await courier.reconcile(entry.id, userTapped: true) else { return XCTFail() }
        posted = await computer.posted
        XCTAssertEqual(posted, [frozen, frozen], "the resend is the same bytes")
        let lookups = await computer.lookups
        XCTAssertEqual(lookups, [package.packageID, package.packageID])
    }

    func testUnknownThatTurnsOutProjectedClearsWithoutResending() async throws {
        let outbox = Outbox(directory: directory)
        let package = try package()
        let entry = try await outbox.freeze(package)
        let computer = FakeComputer(post: [.answer(status: 500, body: Data())],
                                    lookup: [receipt(package.packageID, "projected")])
        let courier = Courier(outbox: outbox, transport: computer)
        _ = await courier.deliver(entry.id)
        guard case .cleared = await courier.reconcile(entry.id, userTapped: true) else { return XCTFail() }
        let posted = await computer.posted
        XCTAssertEqual(posted.count, 1)
    }

    func testConflictIsKeptAndNotRetried() async throws {
        let outbox = Outbox(directory: directory)
        let package = try package()
        let entry = try await outbox.freeze(package)
        let computer = FakeComputer(post: [.answer(status: 409, body: Data(#"{"error":"conflict"}"#.utf8))])
        let courier = Courier(outbox: outbox, transport: computer)
        guard case .kept(let kept) = await courier.deliver(entry.id) else { return XCTFail() }
        XCTAssertEqual(kept.state, .refused)
        _ = await courier.reconcile(entry.id, userTapped: true)
        let lookups = await computer.lookups
        XCTAssertTrue(lookups.isEmpty, "a refused package is left for the user to discard")
    }

    func testOneWaitingPackagePerKind() async throws {
        let outbox = Outbox(directory: directory)
        var package = try package()
        _ = try await outbox.freeze(package)
        package.packageID = CapturePackage.newID()
        do {
            _ = try await outbox.freeze(package)
            XCTFail("a second package of the same kind must not be frozen")
        } catch Outbox.FreezeError.alreadyWaiting {}
        let waiting = await outbox.waiting(kind: "health")
        XCTAssertNotNil(waiting)
    }

    func testOutboxIsExcludedFromBackup() async throws {
        let outbox = Outbox(directory: directory)
        _ = try await outbox.freeze(try package())
        let values = try directory.resourceValues(forKeys: [.isExcludedFromBackupKey])
        XCTAssertEqual(values.isExcludedFromBackup, true)
    }
}
