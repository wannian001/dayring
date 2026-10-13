import CryptoKit
import Foundation

/// A fingerprint of what a read found, so the app does not send the same thing twice. Each record and workout is
/// encoded with sorted keys and the lines are sorted, so the order HealthKit returns them in does not matter.
enum Fingerprint {
    static func of(records: [HealthRecord], workouts: [WorkoutRecord]) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        func lines<T: Encodable>(_ items: [T]) -> [Data] {
            items.compactMap { try? encoder.encode($0) }.sorted { $0.lexicographicallyPrecedes($1) }
        }
        var hash = SHA256()
        hash.update(data: Data("records\n".utf8))
        for line in lines(records) {
            hash.update(data: line)
            hash.update(data: Data("\n".utf8))
        }
        hash.update(data: Data("workouts\n".utf8))
        for line in lines(workouts) {
            hash.update(data: line)
            hash.update(data: Data("\n".utf8))
        }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
