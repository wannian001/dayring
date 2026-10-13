import XCTest
@testable import HealthAIO

final class FingerprintTests: XCTestCase {
    private func fixture() throws -> CapturePackage {
        try JSONDecoder().decode(CapturePackage.self, from: Fixture.data())
    }

    func testStableUnderReordering() throws {
        let package = try fixture()
        let first = Fingerprint.of(records: package.records, workouts: package.workouts)
        var shuffled = package.records
        shuffled.reverse()
        shuffled.swapAt(0, shuffled.count / 2)
        XCTAssertEqual(Fingerprint.of(records: shuffled, workouts: package.workouts), first)
        XCTAssertEqual(first.count, 64)
    }

    func testChangesWhenARecordChanges() throws {
        let package = try fixture()
        let first = Fingerprint.of(records: package.records, workouts: package.workouts)
        var records = package.records
        records[0].value = .text("HKCategoryValueSleepAnalysisAwake")
        XCTAssertNotEqual(Fingerprint.of(records: records, workouts: package.workouts), first)
        XCTAssertNotEqual(Fingerprint.of(records: package.records, workouts: []), first)
        XCTAssertNotEqual(Fingerprint.of(records: Array(package.records.dropLast()), workouts: package.workouts), first)
    }

    func testWorkoutOrderDoesNotMatter() throws {
        let package = try fixture()
        var other = try XCTUnwrap(package.workouts.first)
        other.workoutActivityType = "HKWorkoutActivityTypeWalking"
        other.startDate = "2026-10-13 18:00:00 +1100"
        let a = Fingerprint.of(records: package.records, workouts: [package.workouts[0], other])
        let b = Fingerprint.of(records: package.records, workouts: [other, package.workouts[0]])
        XCTAssertEqual(a, b)
    }
}
