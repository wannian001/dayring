import Foundation

/// One read of Apple Health over a window of days (docs/CAPTURE.md, "Packages").
/// Field names are the wire names; records and workouts use Apple's export.xml attribute names.
struct CapturePackage: Codable, Equatable, Sendable {
    static let schemaName = "healthaio-capture-v1"

    var schema: String
    var packageID: String
    var kind: String
    var createdAt: String
    var timezone: String
    var device: PackageDevice
    var window: PackageWindow
    var records: [HealthRecord]
    var workouts: [WorkoutRecord]

    enum CodingKeys: String, CodingKey {
        case schema
        case packageID = "package_id"
        case kind
        case createdAt = "created_at"
        case timezone, device, window, records, workouts
    }

    /// The exact bytes that are frozen in the outbox and posted. Sorted keys keep them reproducible.
    func encoded() throws -> Data {
        try CapturePackage.encoder().encode(self)
    }

    static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }

    /// `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`, as the server checks it.
    static func isValidID(_ id: String) -> Bool {
        guard let first = id.unicodeScalars.first, id.unicodeScalars.count <= 128 else { return false }
        func plain(_ c: Unicode.Scalar) -> Bool {
            c.isASCII && (CharacterSet.alphanumerics.contains(c))
        }
        guard plain(first) else { return false }
        return id.unicodeScalars.allSatisfy { plain($0) || $0 == "." || $0 == "_" || $0 == "-" }
    }

    static func newID() -> String { "ios-" + UUID().uuidString }
}

struct PackageDevice: Codable, Equatable, Sendable {
    var id: String
    var name: String
    var appVersion: String

    enum CodingKeys: String, CodingKey {
        case id, name
        case appVersion = "app_version"
    }
}

struct PackageWindow: Codable, Equatable, Sendable {
    var startDate: String
    var endDate: String
    var queryStart: String
    var queryEnd: String
    var readCompletedAt: String

    enum CodingKeys: String, CodingKey {
        case startDate = "start_date"
        case endDate = "end_date"
        case queryStart = "query_start"
        case queryEnd = "query_end"
        case readCompletedAt = "read_completed_at"
    }
}

/// A value the export writes as text; the protocol also accepts numbers, so both decode and re-encode as they came.
enum ExportValue: Codable, Hashable, Sendable {
    case text(String)
    case integer(Int64)
    case number(Double)

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let text = try? container.decode(String.self) {
            self = .text(text)
        } else if let integer = try? container.decode(Int64.self) {
            self = .integer(integer)
        } else {
            self = .number(try container.decode(Double.self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .text(let text): try container.encode(text)
        case .integer(let integer): try container.encode(integer)
        case .number(let number): try container.encode(number)
        }
    }

    var text: String {
        switch self {
        case .text(let text): return text
        case .integer(let integer): return String(integer)
        case .number(let number): return NumberText.string(number)
        }
    }
}

struct HealthRecord: Codable, Hashable, Sendable {
    var type: String
    var sourceName: String
    var device: String?
    var unit: String?
    var startDate: String
    var endDate: String
    var value: ExportValue?
    var metadata: [String: String]?
}

struct WorkoutRecord: Codable, Hashable, Sendable {
    var workoutActivityType: String
    var duration: ExportValue?
    var durationUnit: String?
    var sourceName: String
    var device: String?
    var startDate: String
    var endDate: String
    var events: [WorkoutEvent]?
    var statistics: [WorkoutStatistic]?
}

struct WorkoutEvent: Codable, Hashable, Sendable {
    var type: String
    var date: String
}

struct WorkoutStatistic: Codable, Hashable, Sendable {
    var type: String
    var sum: ExportValue?
    var average: ExportValue?
    var minimum: ExportValue?
    var maximum: ExportValue?
    var unit: String?
}
