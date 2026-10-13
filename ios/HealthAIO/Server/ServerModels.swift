import Foundation

/// Answers of `healthaio serve` (docs/CAPTURE.md, "Routes"). Unknown fields are ignored and every field is
/// optional where the server may leave it out, so a newer server does not break an older app.

struct HelloAnswer: Decodable, Sendable {
    var app: String
    var proto: Int?
    var version: String?
    var timezone: String?

    enum CodingKeys: String, CodingKey {
        case app, version, timezone
        case proto = "protocol"
    }
}

struct PairAnswer: Decodable, Sendable {
    var deviceID: String
    var captureToken: String
    var readToken: String
    var server: ServerInfo?

    struct ServerInfo: Decodable, Sendable {
        var version: String?
        var timezone: String?
    }

    enum CodingKeys: String, CodingKey {
        case deviceID = "device_id"
        case captureToken = "capture_token"
        case readToken = "read_token"
        case server
    }
}

struct Receipt: Codable, Equatable, Sendable {
    var ok: Bool?
    var packageID: String
    var status: String
    var landedAt: String?
    var projectedAt: String?
    var rows: [String: Int]?
    var window: ReceiptWindow?
    var error: String?

    struct ReceiptWindow: Codable, Equatable, Sendable {
        var startDate: String?
        var endDate: String?

        enum CodingKeys: String, CodingKey {
            case startDate = "start_date"
            case endDate = "end_date"
        }
    }

    enum CodingKeys: String, CodingKey {
        case ok
        case packageID = "package_id"
        case status
        case landedAt = "landed_at"
        case projectedAt = "projected_at"
        case rows, window, error
    }
}

struct VersionInfo: Decodable, Equatable, Sendable {
    var current: String?
    var latest: String?
    var updateAvailable: Bool?
    var url: String?

    enum CodingKeys: String, CodingKey {
        case current, latest, url
        case updateAvailable = "update_available"
    }
}

struct RenewState: Decodable, Equatable, Sendable {
    var canRenew: Bool?
    var reason: String?
    var running: Bool?
    var last: LastRenew?

    struct LastRenew: Decodable, Equatable, Sendable {
        var at: String?
        var ok: Bool?
        var expiresAt: String?
        var version: String?
        var message: String?

        enum CodingKeys: String, CodingKey {
            case at, ok, version, message
            case expiresAt = "expires_at"
        }
    }

    enum CodingKeys: String, CodingKey {
        case canRenew = "can_renew"
        case reason, running, last
    }
}

struct ServerStatus: Decodable, Sendable {
    var version: String?
    var timezone: String?
    var device: Device?
    var latest: [String: String?]?
    var lastPackage: Receipt?
    var update: VersionInfo?
    var iphone: RenewState?

    struct Device: Decodable, Sendable {
        var id: String?
        var name: String?
        var pairedAt: String?

        enum CodingKeys: String, CodingKey {
            case id, name
            case pairedAt = "paired_at"
        }
    }

    enum CodingKeys: String, CodingKey {
        case version, timezone, device, latest, update, iphone
        case lastPackage = "last_package"
    }
}

struct ErrorAnswer: Decodable, Sendable {
    var error: String?
    var reason: String?
}

/// What came back from one HTTP call, before anyone decides what it means.
enum TransportResult: Sendable, Equatable {
    case answer(status: Int, body: Data)
    case failure(String)
}
