import Foundation

/// Versions like `v0.3.10`. A pre-release (`v0.4.0-rc.1`) sorts below its release and is never offered as an update.
struct SemVer: Comparable, Equatable, Sendable, CustomStringConvertible {
    var numbers: [Int]
    var prerelease: String?

    init?(_ text: String) {
        var raw = text.trimmingCharacters(in: .whitespaces)
        if raw.hasPrefix("v") || raw.hasPrefix("V") { raw.removeFirst() }
        if let plus = raw.firstIndex(of: "+") { raw = String(raw[..<plus]) }
        var pre: String?
        if let dash = raw.firstIndex(of: "-") {
            pre = String(raw[raw.index(after: dash)...])
            raw = String(raw[..<dash])
        }
        let parts = raw.split(separator: ".", omittingEmptySubsequences: false)
        guard (1...3).contains(parts.count) else { return nil }
        var numbers: [Int] = []
        for part in parts {
            guard !part.isEmpty, part.allSatisfy({ $0.isASCII && $0.isNumber }), let n = Int(part) else { return nil }
            numbers.append(n)
        }
        while numbers.count < 3 { numbers.append(0) }
        self.numbers = numbers
        self.prerelease = (pre?.isEmpty ?? true) ? nil : pre
    }

    var isPrerelease: Bool { prerelease != nil }

    var description: String {
        numbers.map(String.init).joined(separator: ".") + (prerelease.map { "-\($0)" } ?? "")
    }

    static func < (a: SemVer, b: SemVer) -> Bool {
        if a.numbers != b.numbers { return a.numbers.lexicographicallyPrecedes(b.numbers) }
        switch (a.prerelease, b.prerelease) {
        case (nil, nil), (nil, _?): return false
        case (_?, nil): return true
        case let (x?, y?): return x.compare(y, options: .numeric) == .orderedAscending
        }
    }

    /// The highest release among tag names like `v0.3.1`; other tags and pre-releases are skipped.
    static func highestReleaseTag(_ names: [String]) -> String? {
        names.filter { $0.hasPrefix("v") }
            .compactMap { name in SemVer(name).flatMap { $0.isPrerelease ? nil : (name, $0) } }
            .max { $0.1 < $1.1 }?.0
    }

    /// True when `candidate` is a release newer than `current`.
    static func isNewer(_ candidate: String?, than current: String) -> Bool {
        guard let candidate, let new = SemVer(candidate), !new.isPrerelease, let old = SemVer(current) else {
            return false
        }
        return old < new
    }
}
