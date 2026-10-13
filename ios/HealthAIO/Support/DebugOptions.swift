#if DEBUG
import Foundation

/// Launch arguments for screenshots and checks without a real phone. Compiled out of Release builds.
///   -HealthAIODebugServer http://127.0.0.1:8790 -HealthAIODebugPairCode 12345678   pair on launch
///   -HealthAIODebugTab panel|capture|settings                                      open on this tab
///   -HealthAIODebugExpiry 2026-10-15T09:00:00+11:00                                pretend signature expiry
///   -HealthAIODebugSendSample YES                                                  post the sample package once
///   -HealthAIODebugNoPrompts YES                                                   no notification explanation sheet
enum DebugOptions {
    private static var args: UserDefaults { .standard }

    static var server: String? { args.string(forKey: "HealthAIODebugServer") }
    static var pairCode: String? { args.string(forKey: "HealthAIODebugPairCode") }
    static var tab: String? { args.string(forKey: "HealthAIODebugTab") }
    static var noPrompts: Bool { args.bool(forKey: "HealthAIODebugNoPrompts") }
    static var sendSample: Bool { args.bool(forKey: "HealthAIODebugSendSample") }

    static var expiry: Date? {
        guard let text = args.string(forKey: "HealthAIODebugExpiry") else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: text) { return date }
        formatter.formatOptions = [.withFullDate]
        return formatter.date(from: text)
    }

    static var pairingLink: PairingLink? {
        guard let server, let pairCode, let url = ServerAddress.normalize(server),
              ServerAddress.isValidCode(pairCode) else { return nil }
        return PairingLink(serverURL: url, code: pairCode)
    }
}
#endif
