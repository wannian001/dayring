import Foundation

/// Problems talking to the computer, in words a person can act on.
enum ServerError: Error, Equatable, LocalizedError {
    case unreachable(String)
    case http(status: Int, message: String?)
    case badAnswer
    case notPaired

    var errorDescription: String? {
        switch self {
        case .unreachable:
            return String(localized: "Can't reach your computer. Check that the phone is on the same Wi-Fi or on Tailscale, and that healthaio serve --lan is running.")
        case .http(401, _), .http(403, _):
            return String(localized: "Your computer did not accept this phone. Pair again in Settings.")
        case .http(_, let message?):
            return message
        case .http(let status, nil):
            return String(localized: "Your computer answered with an error (HTTP \(status)).")
        case .badAnswer:
            return String(localized: "Your computer sent an answer this app can't read. Update healthaio on the computer.")
        case .notPaired:
            return String(localized: "Pair with your computer first, in Settings.")
        }
    }
}

/// Talks to `healthaio serve` over the local network. The capture token only ever travels in an
/// `Authorization: Bearer` header; the read token is not known here at all (it lives in the web view's cookie).
struct ServerClient: Sendable {
    let baseURL: URL
    let captureToken: String?

    static let timeout: TimeInterval = 20

    /// No cookies, no cache, no redirects: an answer always comes from the address the user paired with.
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout * 3
        config.waitsForConnectivity = false
        config.httpShouldSetCookies = false
        config.httpCookieAcceptPolicy = .never
        config.urlCache = nil
        return URLSession(configuration: config, delegate: NoRedirects(), delegateQueue: nil)
    }()

    func url(_ path: String) -> URL {
        baseURL.appending(path: path)
    }

    /// One request; never throws, so callers can decide what a timeout means (for packages it means "unknown").
    func send(_ method: String, _ path: String, body: Data? = nil, auth: Bool = true) async -> TransportResult {
        var request = URLRequest(url: url(path), cachePolicy: .reloadIgnoringLocalCacheData,
                                 timeoutInterval: ServerClient.timeout)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if auth, let captureToken {
            request.setValue("Bearer \(captureToken)", forHTTPHeaderField: "Authorization")
        }
        do {
            let (data, response) = try await ServerClient.session.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .failure("not HTTP") }
            return .answer(status: http.statusCode, body: data)
        } catch {
            return .failure(error.localizedDescription)
        }
    }

    // MARK: Routes

    func hello() async throws -> HelloAnswer {
        try decode(await send("GET", "capture/v1/hello", auth: false), expect: 200)
    }

    func pair(code: String, deviceID: String, deviceName: String) async throws -> PairAnswer {
        let body = try JSONSerialization.data(withJSONObject: [
            "code": code, "device_id": deviceID, "device_name": deviceName,
        ])
        return try decode(await send("POST", "capture/v1/pair", body: body, auth: false), expect: 200)
    }

    func status() async throws -> ServerStatus {
        try decode(await send("GET", "capture/v1/status"), expect: 200)
    }

    func postPackage(_ bytes: Data) async -> TransportResult {
        await send("POST", "capture/v1/packages", body: bytes)
    }

    func lookupPackage(_ id: String) async -> TransportResult {
        await send("GET", "capture/v1/packages/\(id)")
    }

    enum RenewStart: Equatable, Sendable {
        case started
        case alreadyRunning
        case cannot(reason: String?, message: String?)
    }

    func startRenew() async throws -> RenewStart {
        let result = await send("POST", "capture/v1/renew", body: Data("{}".utf8))
        switch result {
        case .answer(202, _), .answer(200, _):
            return .started
        case .answer(409, _):
            return .alreadyRunning
        case .answer(503, let body):
            let answer = try? JSONDecoder().decode(ErrorAnswer.self, from: body)
            return .cannot(reason: answer?.reason, message: answer?.error)
        default:
            throw ServerClient.error(for: result)
        }
    }

    func renewState() async throws -> RenewState {
        try decode(await send("GET", "capture/v1/renew"), expect: 200)
    }

    // MARK: Helpers

    private func decode<T: Decodable>(_ result: TransportResult, expect: Int) throws -> T {
        guard case .answer(let status, let body) = result, status == expect else {
            throw ServerClient.error(for: result)
        }
        do {
            return try JSONDecoder().decode(T.self, from: body)
        } catch {
            throw ServerError.badAnswer
        }
    }

    static func error(for result: TransportResult) -> ServerError {
        switch result {
        case .failure(let text):
            return .unreachable(text)
        case .answer(let status, let body):
            let message = (try? JSONDecoder().decode(ErrorAnswer.self, from: body))?.error
            return .http(status: status, message: message)
        }
    }
}

/// Refuses every redirect, so a request and its token never move to another address.
private final class NoRedirects: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest) async -> URLRequest? {
        nil
    }
}
