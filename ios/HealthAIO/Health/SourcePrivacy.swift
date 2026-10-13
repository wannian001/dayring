import Foundation

/// Apple's own sources carry the name the user gave the device ("Sam's Apple Watch"). The package sends the
/// product instead; third-party app names are kept because the server's merge rules need them.
enum SourcePrivacy {
    struct Source: Equatable, Sendable {
        var sourceName: String
        var device: String?
    }

    /// - Parameters:
    ///   - bundleID: `sourceRevision.source.bundleIdentifier`
    ///   - name: `sourceRevision.source.name`
    ///   - productType: `sourceRevision.productType`, e.g. "Watch7,1" or "iPhone17,3"
    ///   - deviceModel: `device?.model`, e.g. "Watch" or "iPhone"
    static func source(bundleID: String, name: String, productType: String?, deviceModel: String?) -> Source {
        // Case matters: "com.apple.Health" is the Health app itself (entries typed by hand, named "Health"),
        // while the devices are "com.apple.health.<uuid>".
        if bundleID.hasPrefix("com.apple.health") {
            return isWatch(productType: productType, deviceModel: deviceModel)
                ? Source(sourceName: "Apple Watch", device: "Watch")
                : Source(sourceName: "iPhone", device: "iPhone")
        }
        var device = plainModel(deviceModel)
        // Entries typed into Apple's own apps often have no device; the product type still says which one.
        if device == nil, bundleID.lowercased().hasPrefix("com.apple.") {
            if isWatch(productType: productType, deviceModel: nil) {
                device = "Watch"
            } else if productType?.hasPrefix("iPhone") == true {
                device = "iPhone"
            }
        }
        return Source(sourceName: name, device: device)
    }

    static func isWatch(productType: String?, deviceModel: String?) -> Bool {
        if let productType, productType.hasPrefix("Watch") { return true }
        if let deviceModel, deviceModel.localizedCaseInsensitiveContains("watch") { return true }
        return false
    }

    /// A device model is a product name ("iPhone", "Watch"), but keep only short, plain ones to be safe.
    private static func plainModel(_ model: String?) -> String? {
        guard let model = model?.trimmingCharacters(in: .whitespaces), !model.isEmpty, model.count <= 40,
              !model.contains("'"), !model.contains("’")
        else { return nil }
        return model
    }
}
