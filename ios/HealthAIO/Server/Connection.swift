import Foundation
import Observation
import UIKit
import WebKit

/// Which computer this phone is paired with. The address is a plain setting; both tokens are in the Keychain.
@MainActor
@Observable
final class Connection {
    private(set) var serverURL: URL?
    private(set) var pairedAt: Date?
    private(set) var serverVersion: String?
    /// Bumped whenever the pairing changes, so the panel knows to set its cookie again and reload.
    private(set) var generation = 0

    private let defaults: UserDefaults

    private enum Key {
        static let server = "server.url"
        static let pairedAt = "server.pairedAt"
        static let version = "server.version"
        static let installID = "install.id"
    }

    /// Sent to the computer when pairing. It is the model name, never the name the user gave the phone.
    let deviceName = "iPhone"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if let text = defaults.string(forKey: Key.server), let url = URL(string: text),
           Keychain.get(Keychain.captureAccount) != nil {
            serverURL = url
        }
        pairedAt = defaults.object(forKey: Key.pairedAt) as? Date
        serverVersion = defaults.string(forKey: Key.version)
    }

    var isPaired: Bool { serverURL != nil }

    /// A random id made once per install; it names this phone to the computer and in packages.
    var installID: String {
        if let id = defaults.string(forKey: Key.installID) { return id }
        let id = UUID().uuidString
        defaults.set(id, forKey: Key.installID)
        return id
    }

    func client() -> ServerClient? {
        guard let serverURL, let token = Keychain.get(Keychain.captureAccount) else { return nil }
        return ServerClient(baseURL: serverURL, captureToken: token)
    }

    /// Only the panel asks for this, to put it in the web view's cookie store.
    func readToken() -> String? { Keychain.get(Keychain.readAccount) }

    func rememberServerVersion(_ version: String?) {
        guard let version else { return }
        serverVersion = version
        defaults.set(version, forKey: Key.version)
    }

    /// Says hello first (to give a clear message when the address is wrong), then trades the code for tokens.
    func pair(with link: PairingLink) async throws {
        let client = ServerClient(baseURL: link.serverURL, captureToken: nil)
        let hello = try await client.hello()
        guard hello.app == "healthaio" else { throw ServerError.badAnswer }
        let answer: PairAnswer
        do {
            answer = try await client.pair(code: link.code, deviceID: installID, deviceName: deviceName)
        } catch ServerError.http(403, _) {
            throw PairingError.wrongCode
        } catch ServerError.http(410, _) {
            throw PairingError.noCodeOpen
        }
        guard Keychain.set(answer.captureToken, account: Keychain.captureAccount),
              Keychain.set(answer.readToken, account: Keychain.readAccount)
        else { throw PairingError.keychain }
        await clearPanelCookie()
        serverURL = link.serverURL
        pairedAt = Date()
        defaults.set(link.serverURL.absoluteString, forKey: Key.server)
        defaults.set(pairedAt, forKey: Key.pairedAt)
        rememberServerVersion(answer.server?.version ?? hello.version)
        generation += 1
    }

    func unpair() async {
        await clearPanelCookie()
        Keychain.delete(Keychain.captureAccount)
        Keychain.delete(Keychain.readAccount)
        for key in [Key.server, Key.pairedAt, Key.version] { defaults.removeObject(forKey: key) }
        serverURL = nil
        pairedAt = nil
        serverVersion = nil
        generation += 1
    }

    private func clearPanelCookie() async {
        let store = WKWebsiteDataStore.default().httpCookieStore
        for cookie in await store.allCookies() where cookie.name == PanelCookie.name {
            await store.deleteCookie(cookie)
        }
    }
}

enum PairingError: Error, LocalizedError {
    case wrongCode, noCodeOpen, keychain, badInput

    var errorDescription: String? {
        switch self {
        case .wrongCode:
            return String(localized: "That code is not the one your computer shows. Check the 8 digits and try again.")
        case .noCodeOpen:
            return String(localized: "No pairing code is open on your computer. Run healthaio pair there, then try again within 10 minutes.")
        case .keychain:
            return String(localized: "The phone could not store the pairing safely. Try again.")
        case .badInput:
            return String(localized: "Enter the address your computer printed (an IP address, a .local or a .ts.net name) and the 8-digit code.")
        }
    }
}

enum PanelCookie {
    static let name = "healthaio_read"

    static func make(token: String, for url: URL) -> HTTPCookie? {
        guard let host = url.host() else { return nil }
        return HTTPCookie(properties: [
            .name: name, .value: token, .domain: host, .path: "/",
            .expires: Date().addingTimeInterval(400 * 24 * 3600),
        ])
    }
}
