import HealthKit
import XCTest
@testable import HealthAIO

/// Workout effort scores (iOS 18 and later): the names and unit must be the ones Apple's export.xml uses, and the
/// app must neither ask for nor read them where HealthKit does not have them.
final class EffortScoreTests: XCTestCase {
    private let names = ["HKQuantityTypeIdentifierWorkoutEffortScore",
                         "HKQuantityTypeIdentifierEstimatedWorkoutEffortScore"]

    func testNamesAndUnitAreTheExportOnes() throws {
        XCTAssertEqual(HealthNames.effortScores.map(\.identifier.rawValue), names)
        XCTAssertEqual(HealthNames.effortScores.map(\.unit), ["appleEffortScore", "appleEffortScore"])
        XCTAssertFalse(HealthNames.effortScores.contains(where: \.isFood), "effort is not food")

        guard #available(iOS 18.0, *) else { throw XCTSkip("HealthKit has workout effort from iOS 18") }
        // The spelled-out identifiers are the SDK's own.
        XCTAssertEqual(HealthNames.effortScores.map(\.identifier), [.workoutEffortScore, .estimatedWorkoutEffortScore])
        XCTAssertEqual(HKUnit.appleEffortScore().unitString, HealthNames.effortUnit)
    }

    func testReadOnlyWhereHealthKitHasThem() {
        let effort = Set(names)
        let without = HealthNames.quantities(effortScoresAvailable: false).map(\.identifier.rawValue)
        let with = HealthNames.quantities(effortScoresAvailable: true).map(\.identifier.rawValue)
        XCTAssertTrue(effort.isDisjoint(with: without))
        XCTAssertEqual(without, HealthNames.everyday.map(\.identifier.rawValue))
        XCTAssertEqual(with, without + names)

        let current = Set(HealthNames.quantities.map(\.identifier.rawValue))
        let asked = Set(HealthNames.readTypes.map(\.identifier))
        if #available(iOS 18.0, *) {
            XCTAssertTrue(HealthNames.effortScoresAvailable)
            XCTAssertTrue(effort.isSubset(of: current))
            XCTAssertTrue(effort.isSubset(of: asked), "the read permission covers both effort types")
        } else {
            XCTAssertFalse(HealthNames.effortScoresAvailable)
            XCTAssertTrue(effort.isDisjoint(with: current))
            XCTAssertTrue(effort.isDisjoint(with: asked))
        }
    }

    /// Each type's values are read in the unit the record names, and an effort of 7 is sent as "7".
    func testValuesAreReadInTheUnitTheRecordNames() throws {
        guard #available(iOS 18.0, *) else { throw XCTSkip("HealthKit has workout effort from iOS 18") }
        for spec in HealthNames.quantities {
            XCTAssertEqual(spec.hkUnit, HKUnit(from: spec.unit), spec.identifier.rawValue)
            XCTAssertEqual(spec.hkUnit.unitString, spec.unit, spec.identifier.rawValue)
        }
        let spec = try XCTUnwrap(HealthNames.quantities.first { $0.identifier == .workoutEffortScore })
        let rating = HKQuantity(unit: .appleEffortScore(), doubleValue: 7)
        XCTAssertTrue(rating.is(compatibleWith: spec.hkUnit))
        XCTAssertEqual(NumberText.string(rating.doubleValue(for: spec.hkUnit)), "7")
    }

    #if DEBUG
    /// The made-up package carries both scores, spanning its workout, as a real read would.
    func testSamplePackageCarriesEffortForItsWorkout() throws {
        let zone = try XCTUnwrap(TimeZone(identifier: "Australia/Melbourne"))
        let now = try XCTUnwrap(DateFormats(timeZone: zone).parseExport("2026-10-13 21:05:10 +1100"))
        let package = SamplePackage.make(now: now, deviceID: "TEST", appVersion: "0.3.0 (1)", timeZone: zone)
        let run = try XCTUnwrap(package.workouts.first)
        let effort = package.records.filter { names.contains($0.type) }
        XCTAssertEqual(effort.map(\.type), names)
        for record in effort {
            XCTAssertEqual(record.unit, "appleEffortScore")
            XCTAssertEqual(record.startDate, run.startDate)
            XCTAssertEqual(record.endDate, run.endDate)
            XCTAssertEqual(record.sourceName, "Apple Watch")
        }
    }
    #endif
}
