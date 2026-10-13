import XCTest
@testable import HealthAIO

final class CaptureWindowTests: XCTestCase {
    private let melbourne = TimeZone(identifier: "Australia/Melbourne")!

    private func moment(_ text: String) throws -> Date {
        try XCTUnwrap(DateFormats(timeZone: melbourne).parseExport(text))
    }

    private func export(_ date: Date) -> String {
        DateFormats(timeZone: melbourne).exportString(date)
    }

    /// The fixture's window is exactly what the app computes for the moment of that read.
    func testRecentMatchesTheFixture() throws {
        let now = try moment("2026-10-13 21:05:10 +1100")
        let window = try XCTUnwrap(CaptureWindow.recent(now: now, timeZone: melbourne))
        let fixture = try JSONDecoder().decode(CapturePackage.self, from: Fixture.data()).window
        XCTAssertEqual(window.packageWindow(readCompletedAt: now), fixture)
        XCTAssertEqual(window.dayCount, 3)
        XCTAssertEqual(export(window.dayStart), "2026-10-11 00:00:00 +1100")
        XCTAssertEqual(export(window.sleepStart), "2026-10-10 18:00:00 +1100")
    }

    /// Melbourne moves to daylight time at 02:00 on 2026-10-04: the evening before is still +1000.
    func testAcrossTheSpringDSTChange() throws {
        let now = try moment("2026-10-05 12:00:00 +1100")
        let window = try XCTUnwrap(CaptureWindow.recent(now: now, timeZone: melbourne))
        XCTAssertEqual(window.startDate, "2026-10-03")
        XCTAssertEqual(window.endDate, "2026-10-05")
        XCTAssertEqual(export(window.sleepStart), "2026-10-02 18:00:00 +1000")
        XCTAssertEqual(export(window.dayStart), "2026-10-03 00:00:00 +1000")
        XCTAssertEqual(window.dayCount, 3)

        let onTheDay = try XCTUnwrap(CaptureWindow.recent(now: try moment("2026-10-04 10:00:00 +1100"),
                                                          timeZone: melbourne))
        XCTAssertEqual(onTheDay.startDate, "2026-10-02")
        XCTAssertEqual(export(onTheDay.sleepStart), "2026-10-01 18:00:00 +1000")
        // 2026-10-04 has 23 hours; the window still counts 3 calendar days.
        XCTAssertEqual(onTheDay.dayCount, 3)
    }

    /// Daylight time ends at 03:00 on 2026-04-05 (back to 02:00): a 25-hour day.
    func testAcrossTheAutumnDSTChange() throws {
        let window = try XCTUnwrap(CaptureWindow.recent(now: try moment("2026-04-06 08:00:00 +1000"),
                                                        timeZone: melbourne))
        XCTAssertEqual(window.startDate, "2026-04-04")
        XCTAssertEqual(export(window.sleepStart), "2026-04-03 18:00:00 +1100")
        XCTAssertEqual(export(window.dayStart), "2026-04-04 00:00:00 +1100")
    }

    func testCatchUpIsChunkedOldestFirst() throws {
        let now = try moment("2026-10-13 21:05:10 +1100")
        let windows = CaptureWindow.catchUp(now: now, timeZone: melbourne)
        XCTAssertTrue((4...5).contains(windows.count))
        XCTAssertEqual(windows.first?.startDate, "2026-09-30")
        XCTAssertEqual(windows.last?.endDate, "2026-10-13")
        XCTAssertEqual(windows.map(\.dayCount).reduce(0, +), 14)
        for window in windows {
            XCTAssertLessThanOrEqual(window.dayCount, CaptureWindow.maxDays)
            XCTAssertEqual(DateFormats.gregorian(melbourne).component(.hour, from: window.sleepStart), 18)
        }
        // Consecutive, with no gap and no overlap.
        let formats = DateFormats(timeZone: melbourne)
        let calendar = DateFormats.gregorian(melbourne)
        for (a, b) in zip(windows, windows.dropFirst()) {
            let next = try XCTUnwrap(calendar.date(byAdding: .day, value: 1, to: a.endDay))
            XCTAssertEqual(formats.dayString(next), b.startDate)
        }
        // A window that ended before today is read up to its next midnight (still standard time here); today's
        // up to now.
        XCTAssertEqual(export(windows[0].queryEnd), "2026-10-04 00:00:00 +1000")
        XCTAssertEqual(windows.last?.queryEnd, now)
    }

    func testCatchUpAcrossDST() throws {
        let windows = CaptureWindow.catchUp(now: try moment("2026-10-06 09:00:00 +1100"), timeZone: melbourne)
        XCTAssertEqual(windows.first?.startDate, "2026-09-23")
        XCTAssertEqual(windows.last?.endDate, "2026-10-06")
        XCTAssertEqual(windows.map(\.dayCount).reduce(0, +), 14)
        let spanning = try XCTUnwrap(windows.first { $0.startDate <= "2026-10-04" && $0.endDate >= "2026-10-04" })
        XCTAssertLessThanOrEqual(spanning.dayCount, 4)
        let all = windows.flatMap { window -> [String] in
            (0..<window.dayCount).compactMap { offset in
                DateFormats.gregorian(melbourne).date(byAdding: .day, value: offset, to: window.dayStart)
                    .map { DateFormats(timeZone: melbourne).dayString($0) }
            }
        }
        XCTAssertEqual(all.count, Set(all).count)
        XCTAssertTrue(all.contains("2026-10-04"))
    }
}
