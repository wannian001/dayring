import Foundation

/// Sentences built from codes (states, reasons, table names). Literal labels stay in the views; every key is
/// English and translated in Localizable.xcstrings.
enum Strings {
    static func state(_ state: PackageState) -> String {
        switch state {
        case .waiting:
            return String(localized: "Not sent yet.")
        case .unknown:
            return String(localized: "Sent, but no answer came back. The app will ask your computer before sending anything else.")
        case .landed:
            return String(localized: "Stored on your computer, not yet in the tables.")
        case .failed:
            return String(localized: "Stored on your computer, but the rows could not be written. The computer tries again when healthaio serve restarts.")
        case .notFound:
            return String(localized: "Your computer has never received it. Tap Check and retry to send the same package again.")
        case .refused:
            return String(localized: "Your computer refused this package. Discard it; the next read makes a new one.")
        }
    }

    static func stateTitle(_ state: PackageState) -> String {
        switch state {
        case .waiting: return String(localized: "Waiting")
        case .unknown: return String(localized: "No answer")
        case .landed: return String(localized: "Stored")
        case .failed: return String(localized: "Stored, not written")
        case .notFound: return String(localized: "Not received")
        case .refused: return String(localized: "Refused")
        }
    }

    static func receiptStatus(_ status: String) -> String {
        switch status {
        case "projected": return String(localized: "In your tables")
        case "landed": return String(localized: "Stored, not yet in the tables")
        case "failed": return String(localized: "Stored, rows not written")
        default: return status
        }
    }

    /// Tables in the order the dashboard lists them; unknown ones after, by name.
    static func tableOrder(_ a: String, _ b: String) -> Bool {
        let order = ["body_daily", "workouts", "meals", "screen_sessions", "events"]
        let ia = order.firstIndex(of: a) ?? order.count, ib = order.firstIndex(of: b) ?? order.count
        return ia != ib ? ia < ib : a < b
    }

    static func table(_ name: String) -> String {
        switch name {
        case "body_daily": return String(localized: "Daily body (sleep, steps, heart)")
        case "workouts": return String(localized: "Workouts")
        case "meals": return String(localized: "Meals")
        case "screen_sessions": return String(localized: "Screen time")
        case "events": return String(localized: "Calendar")
        default: return name
        }
    }

    /// "2026-10-13T07:14" reads as "2026-10-13 07:14"; a plain day stays as it is.
    static func latestValue(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return "—" }
        return value.replacingOccurrences(of: "T", with: " ")
    }

    static func readOutcome(_ outcome: ReadSummary.Outcome) -> String {
        switch outcome {
        case .sent: return String(localized: "Sent as a package")
        case .nothingNew: return String(localized: "Nothing new since the last read")
        case .empty: return String(localized: "Nothing in Apple Health for these days")
        case .blocked: return String(localized: "Not sent: a package is still waiting")
        case .failed: return String(localized: "Apple Health could not be read")
        }
    }

    /// Why the computer cannot renew, in plain words.
    static func renewReason(_ reason: String?) -> String {
        switch reason {
        case "no_xcode":
            return String(localized: "Your computer has no Xcode, so it cannot sign the app. Install Xcode from the Mac App Store and open it once.")
        case "no_project":
            return String(localized: "Your computer cannot find the app's project (the ios folder of the Health AIO repository). Install healthaio from a copy of the repository.")
        case "no_team":
            return String(localized: "Your computer does not know which Apple account signs the app. Copy ios/Local.example.xcconfig to ios/Local.xcconfig and put your bundle id and Team ID in it.")
        case "not_macos":
            return String(localized: "Only a Mac can sign iPhone apps, and your computer is not a Mac.")
        default:
            return String(localized: "Your computer cannot renew the app right now.")
        }
    }

    static let renewByHand = String(localized: "On your Mac, run: healthaio iphone renew")

    static func bannerLine(_ reason: BannerReason) -> String {
        switch reason {
        case .signature(let days, _):
            switch days {
            case 0: return String(localized: "Health AIO's signature runs out today.")
            case 1: return String(localized: "Health AIO's signature runs out tomorrow.")
            default: return String(localized: "Health AIO's signature runs out in \(days) days.")
            }
        case .newVersion(let version):
            return String(localized: "Health AIO \(version) is available; renewing installs it.")
        }
    }

    static func healthAccess(_ access: HealthReader.Access) -> String {
        switch access {
        case .unavailable: return String(localized: "Not available on this device")
        case .notAsked: return String(localized: "Not asked yet")
        case .asked: return String(localized: "Asked (iOS does not tell apps which types you allowed)")
        }
    }
}
