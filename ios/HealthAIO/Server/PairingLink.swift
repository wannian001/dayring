import Foundation

/// `healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907`, as `healthaio pair` prints it.
struct PairingLink: Equatable, Sendable {
    let serverURL: URL
    let code: String

    static func parse(_ text: String) -> PairingLink? {
        guard let components = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              components.scheme?.lowercased() == "healthaio",
              components.host?.lowercased() == "pair"
        else { return nil }
        let items = components.queryItems ?? []
        guard let address = items.first(where: { $0.name == "url" })?.value,
              let code = items.first(where: { $0.name == "code" })?.value,
              let url = ServerAddress.normalize(address),
              ServerAddress.isValidCode(code)
        else { return nil }
        return PairingLink(serverURL: url, code: code)
    }
}

enum ServerAddress {
    /// Turns what the user typed ("192.168.1.20:8790", "http://mac.local:8790/") into `http://host:port`.
    /// Paths, queries and user names are dropped. Only hosts the server answers to are accepted.
    static func normalize(_ text: String) -> URL? {
        var raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty else { return nil }
        if !raw.contains("://") { raw = "http://" + raw }
        guard let parsed = URLComponents(string: raw),
              let scheme = parsed.scheme?.lowercased(), scheme == "http" || scheme == "https",
              let host = parsed.host, isAllowedHost(host)
        else { return nil }
        var clean = URLComponents()
        clean.scheme = scheme
        clean.host = parsed.host
        clean.port = parsed.port
        return clean.url
    }

    /// The server only answers when the Host header is an IP address, `localhost`, a `.local` or a `.ts.net` name.
    static func isAllowedHost(_ host: String) -> Bool {
        let name = host.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        if name == "localhost" || name.hasSuffix(".local") || name.hasSuffix(".ts.net") { return true }
        return isIPv4(name) || name.contains(":")
    }

    static func isIPv4(_ text: String) -> Bool {
        let parts = text.split(separator: ".", omittingEmptySubsequences: false)
        return parts.count == 4 && parts.allSatisfy { part in
            !part.isEmpty && part.count <= 3 && part.allSatisfy(\.isASCII) && part.allSatisfy(\.isNumber)
                && (Int(part) ?? 256) <= 255
        }
    }

    static func isValidCode(_ code: String) -> Bool {
        code.count == 8 && code.allSatisfy { $0.isASCII && $0.isNumber }
    }

    /// "192.168.1.20:8790", for showing which computer the phone is paired with.
    static func display(_ url: URL) -> String {
        guard let host = url.host() else { return url.absoluteString }
        if let port = url.port { return "\(host):\(port)" }
        return host
    }
}
