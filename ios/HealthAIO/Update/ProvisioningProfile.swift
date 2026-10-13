import Foundation

/// When this copy of the app stops opening. Xcode puts `embedded.mobileprovision` in every app it signs for a
/// device: a CMS-signed envelope around a plain XML property list, so the plist can be cut out by its markers
/// without a CMS decoder. The simulator and App Store builds have no such file, so the expiry is unknown there.
enum ProvisioningProfile {
    struct Info: Equatable, Sendable {
        var expirationDate: Date
        var creationDate: Date?
    }

    static func parse(_ data: Data) -> Info? {
        guard let start = data.range(of: Data("<?xml".utf8)),
              let end = data.range(of: Data("</plist>".utf8), in: start.lowerBound..<data.endIndex)
        else { return nil }
        let plistBytes = data.subdata(in: start.lowerBound..<end.upperBound)
        guard let plist = try? PropertyListSerialization.propertyList(from: plistBytes, format: nil),
              let dict = plist as? [String: Any],
              let expiry = dict["ExpirationDate"] as? Date
        else { return nil }
        return Info(expirationDate: expiry, creationDate: dict["CreationDate"] as? Date)
    }

    static func embedded(in bundle: Bundle = .main) -> Info? {
        guard let url = bundle.url(forResource: "embedded", withExtension: "mobileprovision"),
              let data = try? Data(contentsOf: url) else { return nil }
        return parse(data)
    }
}
