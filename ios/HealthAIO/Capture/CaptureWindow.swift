import Foundation

/// Whole local days to read (docs/CAPTURE.md, "The window"). Every type is read from `start_date` 00:00,
/// except sleep, which starts at 18:00 the evening before, because a night belongs to the day you wake up.
struct CaptureWindow: Equatable, Sendable {
    /// Local midnight of `start_date`.
    let dayStart: Date
    /// Local midnight of `end_date`.
    let endDay: Date
    /// 18:00 on the evening before `start_date`.
    let sleepStart: Date
    /// The moment of the read for a window that ends today; the next midnight for one that ended earlier.
    let queryEnd: Date
    let timeZone: TimeZone

    static let maxDays = 4
    static let recentDays = 3
    static let catchUpDays = 14

    var startDate: String { DateFormats(timeZone: timeZone).dayString(dayStart) }
    var endDate: String { DateFormats(timeZone: timeZone).dayString(endDay) }

    /// Number of local days covered, counted on the calendar so a DST day still counts once.
    var dayCount: Int {
        let calendar = DateFormats.gregorian(timeZone)
        return (calendar.dateComponents([.day], from: dayStart, to: endDay).day ?? 0) + 1
    }

    /// The normal read: the last `days` local days, ending now.
    static func recent(days: Int = recentDays, now: Date, timeZone: TimeZone = .current) -> CaptureWindow? {
        let calendar = DateFormats.gregorian(timeZone)
        let today = calendar.startOfDay(for: now)
        guard let first = calendar.date(byAdding: .day, value: -(max(days, 1) - 1), to: today) else { return nil }
        return make(from: first, to: today, now: now, calendar: calendar)
    }

    /// "Catch up 14 days": consecutive windows of at most `chunk` days, oldest first, the last one ending today.
    static func catchUp(days: Int = catchUpDays, chunk: Int = maxDays, now: Date,
                        timeZone: TimeZone = .current) -> [CaptureWindow] {
        let calendar = DateFormats.gregorian(timeZone)
        let today = calendar.startOfDay(for: now)
        let size = min(max(chunk, 1), maxDays)
        var windows: [CaptureWindow] = []
        var offset = -(max(days, 1) - 1)
        while offset <= 0 {
            let last = min(offset + size - 1, 0)
            guard let first = calendar.date(byAdding: .day, value: offset, to: today),
                  let end = calendar.date(byAdding: .day, value: last, to: today),
                  let window = make(from: calendar.startOfDay(for: first), to: calendar.startOfDay(for: end),
                                    now: now, calendar: calendar)
            else { break }
            windows.append(window)
            offset = last + 1
        }
        return windows
    }

    private static func make(from first: Date, to last: Date, now: Date, calendar: Calendar) -> CaptureWindow? {
        guard let evening = calendar.date(byAdding: .day, value: -1, to: first),
              let sleepStart = calendar.date(bySettingHour: 18, minute: 0, second: 0, of: evening),
              let nextMidnight = calendar.date(byAdding: .day, value: 1, to: last)
        else { return nil }
        return CaptureWindow(dayStart: first, endDay: last, sleepStart: sleepStart,
                             queryEnd: min(now, calendar.startOfDay(for: nextMidnight)),
                             timeZone: calendar.timeZone)
    }

    /// The `window` object of a package; `readCompletedAt` is when the last query returned.
    func packageWindow(readCompletedAt: Date) -> PackageWindow {
        let formats = DateFormats(timeZone: timeZone)
        return PackageWindow(startDate: startDate, endDate: endDate,
                             queryStart: formats.exportString(sleepStart),
                             queryEnd: formats.exportString(queryEnd),
                             readCompletedAt: formats.exportString(readCompletedAt))
    }
}
