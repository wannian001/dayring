import Foundation

/// Answers of the healthaio CLI (the contract is in mac/README.md, "The commands it relies on"). Every field is read as optional on purpose:
/// an older or newer Python side may leave one out, and the app shows what it has instead of failing.
typealias JSONObject = [String: Any]

enum JSONParse {
    /// The JSON object a command printed. Lines printed before it (a warning from Python or a library) are skipped.
    static func object(from data: Data) -> JSONObject? {
        if let object = parse(data) { return object }
        guard let text = String(data: data, encoding: .utf8) else { return nil }
        for line in text.split(whereSeparator: \.isNewline).reversed() {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("{"), let object = parse(Data(trimmed.utf8)) { return object }
        }
        if let start = text.firstIndex(of: "{"), let end = text.lastIndex(of: "}"), start < end {
            return parse(Data(text[start...end].utf8))
        }
        return nil
    }

    private static func parse(_ data: Data) -> JSONObject? {
        guard !data.isEmpty else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? JSONObject
    }
}

extension Dictionary where Key == String, Value == Any {
    func string(_ key: String) -> String? {
        switch self[key] {
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        default: return nil
        }
    }

    func bool(_ key: String) -> Bool? { (self[key] as? NSNumber)?.boolValue }

    func int(_ key: String) -> Int? {
        if let n = self[key] as? NSNumber { return n.intValue }
        return string(key).flatMap { Int($0) }
    }

    func object(_ key: String) -> JSONObject? { self[key] as? JSONObject }
    func objects(_ key: String) -> [JSONObject] { self[key] as? [JSONObject] ?? [] }
    func strings(_ key: String) -> [String] { (self[key] as? [Any])?.compactMap { $0 as? String } ?? [] }
    func date(_ key: String) -> Date? { string(key).flatMap(ISODate.parse) }
}

/// ISO 8601 times as the Python side writes them, with or without an offset or seconds.
enum ISODate {
    private static let withOffset: [ISO8601DateFormatter] = {
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return [plain, fractional]
    }()

    private static let local: [DateFormatter] = ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd'T'HH:mm", "yyyy-MM-dd HH:mm:ss Z", "yyyy-MM-dd"].map {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = $0
        return f
    }

    static func parse(_ text: String) -> Date? {
        let t = text.trimmingCharacters(in: .whitespaces)
        for f in withOffset { if let d = f.date(from: t) { return d } }
        for f in local { if let d = f.date(from: t) { return d } }
        return nil
    }
}

struct CollectResult {
    struct Source: Identifiable {
        let name: String
        let ok: Bool
        let message: String
        var id: String { name }
    }

    let ok: Bool
    let at: Date?
    let sources: [Source]

    init?(_ json: JSONObject?) {
        guard let json, json["ok"] != nil || json["sources"] != nil else { return nil }
        ok = json.bool("ok") ?? false
        at = json.date("at")
        sources = json.objects("sources").map {
            Source(name: $0.string("name") ?? "?", ok: $0.bool("ok") ?? false, message: $0.string("message") ?? "")
        }
    }
}

struct Device: Identifiable {
    let id: String
    let name: String
    let pairedAt: Date?
    let lastSeen: Date?

    init(_ json: JSONObject) {
        id = json.string("id") ?? UUID().uuidString
        name = json.string("name") ?? "iPhone"
        pairedAt = json.date("paired_at")
        lastSeen = json.date("last_seen")
    }

    static func list(_ json: JSONObject?) -> [Device] { json?.objects("devices").map(Device.init) ?? [] }
}

/// The last `iphone renew`, as `status` and `iphone status` report it.
struct RenewRecord {
    let at: Date?
    let ok: Bool
    let expiresAt: Date?
    let version: String?
    let message: String?

    init(_ json: JSONObject) {
        at = json.date("at")
        ok = json.bool("ok") ?? false
        expiresAt = json.date("expires_at")
        version = json.string("version")
        message = json.string("message")
    }
}

struct IPhoneInfo {
    let canRenew: Bool
    let reason: String?
    let running: Bool
    let last: RenewRecord?

    init(_ json: JSONObject) {
        canRenew = json.bool("can_renew") ?? false
        reason = json.string("reason")
        running = json.bool("running") ?? false
        last = json.object("last").map(RenewRecord.init)
    }
}

/// `update --check --json`, or the cached copy inside `status`.
struct UpdateInfo {
    let current: String?
    let latest: String?
    let available: Bool
    let url: String?
    let notes: String?
    let checkedAt: Date?
    let install: String?
    let canUpdate: Bool
    let reason: String?

    init(_ json: JSONObject) {
        current = json.string("current")
        latest = json.string("latest")
        available = (json.bool("update_available") ?? false) && json.string("latest") != nil
        url = json.string("url")
        notes = json.string("notes")
        checkedAt = json.date("checked_at")
        install = json.string("install")
        canUpdate = json.bool("can_update") ?? false
        reason = json.string("reason")
    }

    /// The first lines of the release notes, enough for an alert.
    func notesExcerpt(lines: Int = 6) -> String? {
        guard let notes else { return nil }
        let all = notes.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        guard !all.isEmpty else { return nil }
        let head = all.prefix(lines).joined(separator: "\n")
        return all.count > lines ? head + "\n…" : head
    }
}

struct StatusInfo {
    let version: String?
    let port: Int?
    let collect: CollectResult?
    let devices: [Device]
    let fullDiskAccess: Bool?
    let iphone: IPhoneInfo?
    let update: UpdateInfo?

    init(_ json: JSONObject) {
        version = json.string("version")
        port = json.int("port")
        collect = CollectResult(json.object("collect"))
        devices = Device.list(json)
        fullDiskAccess = json.bool("full_disk_access")
        iphone = json.object("iphone").map(IPhoneInfo.init)
        update = json.object("update").map(UpdateInfo.init)
    }
}

/// `update --yes --json`.
struct UpdateOutcome {
    let ok: Bool
    let from: String?
    let to: String?
    let macAppChanged: Bool
    let iosAppChanged: Bool
    let message: String?

    init(_ json: JSONObject) {
        ok = json.bool("ok") ?? false
        from = json.string("from")
        to = json.string("to")
        let changed = json.object("changed") ?? [:]
        macAppChanged = changed.bool("mac_app") ?? false
        iosAppChanged = changed.bool("ios_app") ?? false
        message = json.string("message") ?? json.string("error")
    }
}

/// `iphone renew --json`.
struct RenewOutcome {
    let ok: Bool
    let expiresAt: Date?
    let message: String?

    init(_ json: JSONObject) {
        ok = json.bool("ok") ?? false
        expiresAt = json.date("expires_at")
        message = json.string("message") ?? json.string("error")
    }
}

/// `pair --json`.
struct PairInfo {
    let code: String
    let expiresAt: Date?
    let urls: [String]
    let link: String
    let serverRunning: Bool
    let serverLAN: Bool

    init?(_ json: JSONObject?) {
        guard let json, let code = json.string("code"), !code.isEmpty else { return nil }
        self.code = code
        expiresAt = json.date("expires_at")
        urls = json.strings("urls")
        serverRunning = json.bool("server_running") ?? false
        serverLAN = json.bool("server_lan") ?? false
        if let link = json.string("link"), !link.isEmpty {
            self.link = link
        } else {
            // the same shape the Python side prints, in case an older one leaves the link out
            let allowed = CharacterSet.alphanumerics
            let url = urls.first?.addingPercentEncoding(withAllowedCharacters: allowed) ?? ""
            link = "healthaio://pair?url=\(url)&code=\(code)"
        }
    }

    /// "48213907" shown as "4821 3907".
    var groupedCode: String {
        guard code.count == 8 else { return code }
        return String(code.prefix(4)) + " " + String(code.suffix(4))
    }
}
