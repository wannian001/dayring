import HealthKit
import XCTest
@testable import HealthAIO

/// VO2 max (cardio fitness): the name and unit must be the ones Apple's export.xml uses, and its values must reach
/// the package with both unchanged, as resting heart rate does.
final class VO2MaxTests: XCTestCase {
    private let typeName = "HKQuantityTypeIdentifierVO2Max"
    /// The export's unit attribute; the dot is U+00B7 MIDDLE DOT.
    private let exportUnit = "mL/min\u{00B7}kg"

    private func vo2MaxSpec() throws -> HealthNames.QuantitySpec {
        try XCTUnwrap(HealthNames.everyday.first { $0.identifier == .vo2Max })
    }

    func testReadOnEveryPhone() throws {
        let spec = try vo2MaxSpec()
        XCTAssertEqual(spec.identifier.rawValue, typeName)
        XCTAssertFalse(spec.isFood, "VO2 max is not food")
        for available in [false, true] {
            let read = HealthNames.quantities(effortScoresAvailable: available).map(\.identifier)
            XCTAssertEqual(read.filter { $0 == .vo2Max }.count, 1, "read with or without the effort scores")
        }
        let asked = Set(HealthNames.readTypes.map(\.identifier))
        XCTAssertTrue(asked.contains(typeName), "the read permission covers VO2 max")
    }

    func testUnitIsTheExportOne() throws {
        let spec = try vo2MaxSpec()
        XCTAssertEqual(spec.unit, exportUnit)
        XCTAssertEqual(spec.unit, "mL/min·kg")
        let nonASCII = spec.unit.unicodeScalars.map(\.value).filter { $0 > 0x7F }
        XCTAssertEqual(nonASCII, [0xB7], "one middle dot, nothing else")
        XCTAssertEqual(HealthNames.vo2MaxUnit, exportUnit)
    }

    /// The unit is built from its parts, fits the type, and HealthKit spells it as the export does.
    func testUnitFitsTheType() throws {
        let spec = try vo2MaxSpec()
        let built = HKUnit.literUnit(with: .milli)
            .unitDivided(by: HKUnit.gramUnit(with: .kilo).unitMultiplied(by: .minute()))
        XCTAssertEqual(spec.hkUnit, built)
        XCTAssertTrue(HKQuantityType(.vo2Max).is(compatibleWith: spec.hkUnit))
        XCTAssertEqual(spec.hkUnit.unitString, exportUnit)

        let reading = HKQuantity(unit: spec.hkUnit, doubleValue: 41.8)
        XCTAssertTrue(reading.is(compatibleWith: spec.hkUnit))
        XCTAssertEqual(NumberText.string(reading.doubleValue(for: spec.hkUnit)), "41.8")
        // A value stored in another volume unit is still sent in the export's unit.
        let litres = HKUnit.liter().unitDivided(by: HKUnit.gramUnit(with: .kilo).unitMultiplied(by: .minute()))
        XCTAssertEqual(NumberText.string(HKQuantity(unit: litres, doubleValue: 0.0418).doubleValue(for: spec.hkUnit)),
                       "41.8")
    }

    /// A VO2 max sample goes through the reader's own conversion into a package, and the package's bytes and its
    /// decoded copy keep the type name and the unit string exactly.
    func testPackageKeepsTypeAndUnit() throws {
        let spec = try vo2MaxSpec()
        let zone = try XCTUnwrap(TimeZone(identifier: "Australia/Melbourne"))
        let formats = DateFormats(timeZone: zone)
        let now = try XCTUnwrap(formats.parseExport("2026-10-13 21:05:10 +1100"))
        let measured = try XCTUnwrap(formats.parseExport("2026-10-12 07:31:00 +1100"))
        let window = try XCTUnwrap(CaptureWindow.recent(now: now, timeZone: zone))
        let sample = HKQuantitySample(type: HKQuantityType(.vo2Max),
                                      quantity: HKQuantity(unit: spec.hkUnit, doubleValue: 41.8),
                                      start: measured, end: measured, metadata: ["HKTimeZone": zone.identifier])

        let records = HealthReader.quantityRecords([sample], spec: spec, formats: formats) { _ in
            SourcePrivacy.Source(sourceName: "Apple Watch", device: "Watch")
        }
        let record = try XCTUnwrap(records.first)
        XCTAssertEqual(records.count, 1)
        XCTAssertEqual(record.type, typeName)
        XCTAssertEqual(record.unit, exportUnit)
        XCTAssertEqual(record.value, .text("41.8"))
        XCTAssertEqual(record.startDate, "2026-10-12 07:31:00 +1100")
        XCTAssertEqual(record.endDate, "2026-10-12 07:31:00 +1100")
        XCTAssertEqual(record.metadata, ["HKTimeZone": "Australia/Melbourne"])

        let package = CapturePackage(
            schema: CapturePackage.schemaName, packageID: CapturePackage.newID(), kind: "health",
            createdAt: formats.isoString(now), timezone: zone.identifier,
            device: PackageDevice(id: "TEST", name: "iPhone", appVersion: "0.3.0 (1)"),
            window: window.packageWindow(readCompletedAt: now), records: records, workouts: [])
        let bytes = try package.encoded()
        let text = try XCTUnwrap(String(data: bytes, encoding: .utf8))
        XCTAssertTrue(text.contains(#""type":"HKQuantityTypeIdentifierVO2Max""#), text)
        XCTAssertTrue(text.contains("\"unit\":\"mL/min\u{00B7}kg\""), "sent as UTF-8, nothing escaped: \(text)")
        let back = try JSONDecoder().decode(CapturePackage.self, from: bytes)
        XCTAssertEqual(back, package)
        XCTAssertEqual(back.records.map(\.type), [typeName])
        XCTAssertEqual(back.records.map(\.unit), [exportUnit])
    }

    #if DEBUG
    /// The made-up package has the watch's estimate at the end of its outdoor run, in the export's unit.
    func testSamplePackageCarriesVO2Max() throws {
        let zone = try XCTUnwrap(TimeZone(identifier: "Australia/Melbourne"))
        let now = try XCTUnwrap(DateFormats(timeZone: zone).parseExport("2026-10-13 21:05:10 +1100"))
        let package = SamplePackage.make(now: now, deviceID: "TEST", appVersion: "0.3.0 (1)", timeZone: zone)
        let run = try XCTUnwrap(package.workouts.first)
        let vo2 = package.records.filter { $0.type == typeName }
        XCTAssertEqual(vo2.count, 1)
        let record = try XCTUnwrap(vo2.first)
        XCTAssertEqual(record.unit, exportUnit)
        XCTAssertEqual(record.value?.text, "41.8")
        XCTAssertEqual(record.startDate, run.endDate)
        XCTAssertEqual(record.sourceName, "Apple Watch")
    }
    #endif
}
