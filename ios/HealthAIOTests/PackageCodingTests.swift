import XCTest
@testable import HealthAIO

/// The shared example package (tests/fixtures/capture/health_3days.json) is read straight from the repository,
/// so the Python tests and these tests always look at the same file.
enum Fixture {
    static var url: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()      // HealthAIOTests
            .deletingLastPathComponent()      // ios
            .deletingLastPathComponent()      // repository root
            .appending(path: "tests/fixtures/capture/health_3days.json")
    }

    static func data() throws -> Data {
        try Data(contentsOf: url)
    }
}

final class PackageCodingTests: XCTestCase {
    func testDecodesTheFixture() throws {
        let package = try JSONDecoder().decode(CapturePackage.self, from: Fixture.data())
        XCTAssertEqual(package.schema, CapturePackage.schemaName)
        XCTAssertEqual(package.kind, "health")
        XCTAssertTrue(CapturePackage.isValidID(package.packageID))
        XCTAssertEqual(package.window.startDate, "2026-10-11")
        XCTAssertEqual(package.window.queryStart, "2026-10-10 18:00:00 +1100")
        XCTAssertEqual(package.records.count, 29)
        XCTAssertEqual(package.workouts.count, 1)

        let food = try XCTUnwrap(package.records.first { $0.type == "HKQuantityTypeIdentifierDietaryEnergyConsumed" })
        XCTAssertEqual(food.metadata?["HKFoodMeal"], "Lunch")
        XCTAssertEqual(food.value?.text, "640")
        XCTAssertEqual(food.sourceName, "MyFitnessPal")

        let run = try XCTUnwrap(package.workouts.first)
        XCTAssertEqual(run.events?.map(\.type), ["HKWorkoutEventTypePause", "HKWorkoutEventTypeResume"])
        XCTAssertEqual(run.statistics?.first { $0.type == "HKQuantityTypeIdentifierHeartRate" }?.average?.text, "148")
    }

    /// Decode, encode, and compare as JSON values: nothing added, nothing lost, nothing changed.
    func testReencodesWithoutLosingFields() throws {
        let original = try Fixture.data()
        let package = try JSONDecoder().decode(CapturePackage.self, from: original)
        let encoded = try package.encoded()
        let before = try JSONSerialization.jsonObject(with: original) as? NSDictionary
        let after = try JSONSerialization.jsonObject(with: encoded) as? NSDictionary
        XCTAssertNotNil(before)
        XCTAssertEqual(before, after)
        XCTAssertEqual(try JSONDecoder().decode(CapturePackage.self, from: encoded), package)
    }

    func testValuesMayBeNumbers() throws {
        let json = #"{"type":"HKQuantityTypeIdentifierBodyMass","sourceName":"Health","unit":"kg","startDate":"2026-10-12 07:00:00 +1100","endDate":"2026-10-12 07:00:00 +1100","value":72.4}"#
        let record = try JSONDecoder().decode(HealthRecord.self, from: Data(json.utf8))
        XCTAssertEqual(record.value, .number(72.4))
        XCTAssertEqual(record.value?.text, "72.4")
        let back = try JSONSerialization.jsonObject(with: JSONEncoder().encode(record)) as? [String: Any]
        XCTAssertEqual(back?["value"] as? Double, 72.4)

        let count = try JSONDecoder().decode(ExportValue.self, from: Data("812".utf8))
        XCTAssertEqual(count, .integer(812))
    }

    func testPackageIDRule() {
        XCTAssertTrue(CapturePackage.isValidID(CapturePackage.newID()))
        XCTAssertTrue(CapturePackage.isValidID("ios-sample.1_a"))
        XCTAssertFalse(CapturePackage.isValidID(""))
        XCTAssertFalse(CapturePackage.isValidID("-starts-with-dash"))
        XCTAssertFalse(CapturePackage.isValidID("has space"))
        XCTAssertFalse(CapturePackage.isValidID("ünicode"))
        XCTAssertFalse(CapturePackage.isValidID(String(repeating: "a", count: 129)))
    }

    func testNumberText() {
        XCTAssertEqual(NumberText.string(812), "812")
        XCTAssertEqual(NumberText.string(72.4), "72.4")
        XCTAssertEqual(NumberText.string(31.5), "31.5")
        XCTAssertEqual(NumberText.string(0.123456), "0.1235")
    }

    #if DEBUG
    func testSamplePackageIsValid() throws {
        let now = try XCTUnwrap(DateFormats(timeZone: TimeZone(identifier: "Australia/Melbourne")!)
            .parseExport("2026-10-13 21:05:10 +1100"))
        let package = SamplePackage.make(now: now, deviceID: "TEST", appVersion: "0.3.0 (1)",
                                         timeZone: TimeZone(identifier: "Australia/Melbourne")!)
        XCTAssertTrue(CapturePackage.isValidID(package.packageID))
        XCTAssertEqual(package.window.startDate, "2026-10-11")
        XCTAssertFalse(package.records.isEmpty)
        XCTAssertEqual(package.workouts.count, 1)
        XCTAssertFalse(package.records.contains { $0.sourceName.contains("'") })
    }
    #endif
}
