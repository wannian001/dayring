import Foundation

/// The two calls the outbox needs; `ServerClient` answers them, tests use a fake.
protocol CaptureTransport: Sendable {
    func postPackage(_ bytes: Data) async -> TransportResult
    func lookupPackage(_ id: String) async -> TransportResult
}

extension ServerClient: CaptureTransport {}

/// What an answer means for a frozen package (docs/CAPTURE.md, "What the app does").
enum OutboxPolicy {
    enum Decision: Equatable, Sendable {
        case clear(Receipt)
        case keep(PackageState, String?)
        /// Only from a lookup: the computer has never seen the package.
        case notFound
    }

    /// After `POST /capture/v1/packages`. Clear only on 200, `ok`, the same id and `projected`.
    static func afterPost(id: String, result: TransportResult) -> Decision {
        switch result {
        case .failure:
            return .keep(.unknown, nil)
        case .answer(let status, let body):
            switch status {
            case 200, 201:
                return fromReceipt(id: id, body: body)
            case 409:
                return .keep(.refused, errorText(body) ?? String(localized: "Your computer already has a different package with this id."))
            case 400, 413, 415, 422:
                return .keep(.refused, errorText(body))
            case 401, 403:
                // Not stored; resending the same bytes after pairing again is safe.
                return .keep(.waiting, String(localized: "Your computer did not accept this phone. Pair again in Settings."))
            default:
                // A 5xx or anything else: the package may or may not be stored.
                return .keep(.unknown, errorText(body))
            }
        }
    }

    /// After `GET /capture/v1/packages/<id>`. Asking never creates anything on the computer.
    static func afterLookup(id: String, result: TransportResult) -> Decision {
        switch result {
        case .failure:
            return .keep(.unknown, nil)
        case .answer(200, let body):
            if let receipt = try? JSONDecoder().decode(Receipt.self, from: body),
               receipt.packageID == id, receipt.status == "not_found" {
                return .notFound
            }
            return fromReceipt(id: id, body: body)
        case .answer(404, let body):
            if let receipt = try? JSONDecoder().decode(Receipt.self, from: body), receipt.status == "not_found" {
                return .notFound
            }
            return .keep(.unknown, errorText(body))
        case .answer(401, _), .answer(403, _):
            return .keep(.waiting, String(localized: "Your computer did not accept this phone. Pair again in Settings."))
        case .answer(_, let body):
            return .keep(.unknown, errorText(body))
        }
    }

    private static func fromReceipt(id: String, body: Data) -> Decision {
        guard let receipt = try? JSONDecoder().decode(Receipt.self, from: body), receipt.packageID == id else {
            return .keep(.unknown, nil)
        }
        switch receipt.status {
        case "projected" where receipt.ok == true:
            return .clear(receipt)
        case "landed":
            return .keep(.landed, nil)
        case "failed":
            return .keep(.failed, receipt.error)
        default:
            return .keep(.unknown, receipt.error)
        }
    }

    private static func errorText(_ body: Data) -> String? {
        (try? JSONDecoder().decode(ErrorAnswer.self, from: body))?.error
    }
}

/// Moves frozen packages to the computer, following `OutboxPolicy`.
struct Courier: Sendable {
    let outbox: Outbox
    let transport: any CaptureTransport

    enum Outcome: Equatable, Sendable {
        case cleared(Receipt)
        case kept(OutboxEntry)
        case missing
    }

    /// The first post of a freshly frozen package.
    func deliver(_ id: String) async -> Outcome {
        guard let entry = await outbox.entry(id), let bytes = try? await outbox.bytes(id) else { return .missing }
        let result = await transport.postPackage(bytes)
        return await apply(OutboxPolicy.afterPost(id: id, result: result), to: entry)
    }

    /// Asks the computer what happened to a waiting package. The same bytes are sent again only when the computer
    /// has never seen it and `userTapped` is true; a refused package is left for the user to discard.
    func reconcile(_ id: String, userTapped: Bool) async -> Outcome {
        guard let entry = await outbox.entry(id) else { return .missing }
        if entry.state == .refused { return .kept(entry) }
        let lookup = await transport.lookupPackage(id)
        let decision = OutboxPolicy.afterLookup(id: id, result: lookup)
        if decision == .notFound, userTapped {
            return await deliver(id)
        }
        return await apply(decision, to: entry)
    }

    private func apply(_ decision: OutboxPolicy.Decision, to entry: OutboxEntry) async -> Outcome {
        var entry = entry
        entry.lastTriedAt = Date()
        switch decision {
        case .clear(let receipt):
            await outbox.remove(entry.id)
            return .cleared(receipt)
        case .keep(let state, let message):
            entry.state = state
            entry.message = message
        case .notFound:
            entry.state = .notFound
            entry.message = nil
        }
        try? await outbox.save(entry)
        return .kept(entry)
    }
}
