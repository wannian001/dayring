import Foundation

/// The date shapes the capture protocol uses. Each formatter is made for one read and not shared across tasks,
/// and every one is pinned to the Gregorian calendar and en_US_POSIX so a phone set to another calendar or
/// locale still writes `2026-10-13`.
struct DateFormats {
    let timeZone: TimeZone
    private let export: DateFormatter
    private let day: DateFormatter
    private let offset: DateFormatter

    init(timeZone: TimeZone = .current) {
        self.timeZone = timeZone
        export = DateFormats.formatter("yyyy-MM-dd HH:mm:ss Z", timeZone)
        day = DateFormats.formatter("yyyy-MM-dd", timeZone)
        offset = DateFormats.formatter("yyyy-MM-dd'T'HH:mm:ssxxx", timeZone)
    }

    /// `2026-10-13 21:05:10 +1100`, as in Apple's export.xml.
    func exportString(_ date: Date) -> String { export.string(from: date) }
    /// `2026-10-13`, a whole local day.
    func dayString(_ date: Date) -> String { day.string(from: date) }
    /// `2026-10-13T21:05:11+11:00`, for `created_at`.
    func isoString(_ date: Date) -> String { offset.string(from: date) }

    func parseDay(_ text: String) -> Date? { day.date(from: text) }
    func parseExport(_ text: String) -> Date? { export.date(from: text) }

    static func gregorian(_ timeZone: TimeZone) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        calendar.locale = Locale(identifier: "en_US_POSIX")
        return calendar
    }

    private static func formatter(_ format: String, _ timeZone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = gregorian(timeZone)
        f.timeZone = timeZone
        f.dateFormat = format
        return f
    }
}

/// Numbers in records are written the way the export writes them: no trailing zeros, a dot for decimals.
enum NumberText {
    static func string(_ value: Double) -> String {
        guard value.isFinite else { return "0" }
        if value == value.rounded(), abs(value) < 1e15 {
            return String(Int64(value))
        }
        var text = String(format: "%.4f", value)
        while text.hasSuffix("0") { text.removeLast() }
        if text.hasSuffix(".") { text.removeLast() }
        return text
    }
}

/// The local day as a key, for "once a day" decisions.
enum LocalDay {
    static func key(_ date: Date = Date(), timeZone: TimeZone = .current) -> String {
        DateFormats(timeZone: timeZone).dayString(date)
    }
}
