import Foundation

/// "Open at login": one LaunchAgent of our own, ~/Library/LaunchAgents/io.github.wannian001.healthaio.mac.plist,
/// that opens this app when you log in. Only that one file is ever written or removed; nothing is loaded with
/// launchctl, launchd reads it at the next login.
enum LoginItem {
    static let label = "io.github.wannian001.healthaio.mac"

    static var plistURL: URL {
        Paths.home.appendingPathComponent("Library/LaunchAgents/\(label).plist")
    }

    static var isEnabled: Bool { FileManager.default.fileExists(atPath: plistURL.path) }

    static func setEnabled(_ enabled: Bool) throws {
        if enabled {
            try write()
        } else if isEnabled, isOurs() {
            try FileManager.default.removeItem(at: plistURL)
            AppLog.info("login item removed")
        }
    }

    /// The app may have been rebuilt or moved since the file was written; point it at this copy.
    static func refreshIfEnabled() {
        guard isEnabled, isOurs(), currentAppPath() != Bundle.main.bundlePath else { return }
        try? write()
    }

    private static func write() throws {
        let plist: [String: Any] = [
            "Label": label,
            "ProgramArguments": ["/usr/bin/open", "-a", Bundle.main.bundlePath],
            "RunAtLoad": true,
            "LimitLoadToSessionType": "Aqua",
        ]
        let data = try PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0)
        try FileManager.default.createDirectory(at: plistURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: plistURL, options: .atomic)
        AppLog.info("login item written")
    }

    private static func contents() -> [String: Any]? {
        guard let data = try? Data(contentsOf: plistURL) else { return nil }
        return (try? PropertyListSerialization.propertyList(from: data, format: nil)) as? [String: Any]
    }

    private static func isOurs() -> Bool { contents()?["Label"] as? String == label }

    private static func currentAppPath() -> String? {
        (contents()?["ProgramArguments"] as? [String])?.last
    }
}
