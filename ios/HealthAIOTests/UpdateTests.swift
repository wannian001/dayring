import XCTest
@testable import HealthAIO

final class ProvisioningProfileTests: XCTestCase {
    /// A stand-in for embedded.mobileprovision: binary CMS bytes around a plain XML plist.
    private func blob(plist: String) -> Data {
        var data = Data([0x30, 0x82, 0x2A, 0x5B, 0x06, 0x09, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x07, 0x02, 0xA0])
        data.append(contentsOf: (0..<200).map { UInt8($0 % 251) })
        data.append(Data(plist.utf8))
        data.append(Data([0xA0, 0x82, 0x0B, 0xFE, 0x30, 0x82, 0x05, 0x00, 0x3C, 0x2F]))  // includes a stray "</"
        return data
    }

    private let plist = """
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>AppIDName</key><string>Health AIO</string>
        <key>CreationDate</key><date>2026-10-13T09:15:00Z</date>
        <key>ExpirationDate</key><date>2026-10-20T09:15:00Z</date>
        <key>Name</key><string>Example Team Provisioning Profile</string>
    </dict>
    </plist>
    """

    func testReadsExpiryFromACMSLikeBlob() throws {
        let info = try XCTUnwrap(ProvisioningProfile.parse(blob(plist: plist)))
        XCTAssertEqual(info.expirationDate, ISO8601DateFormatter().date(from: "2026-10-20T09:15:00Z"))
        XCTAssertEqual(info.creationDate, ISO8601DateFormatter().date(from: "2026-10-13T09:15:00Z"))
    }

    func testMissingOrBrokenProfileIsUnknown() {
        XCTAssertNil(ProvisioningProfile.parse(Data()))
        XCTAssertNil(ProvisioningProfile.parse(Data([0x30, 0x82, 0x00, 0x01])))
        XCTAssertNil(ProvisioningProfile.parse(blob(plist: String(plist.dropLast(10)))))
        XCTAssertNil(ProvisioningProfile.parse(blob(plist: plist.replacingOccurrences(of: "ExpirationDate", with: "Other"))))
        // The simulator has no embedded.mobileprovision at all.
        XCTAssertNil(ProvisioningProfile.embedded(in: Bundle(for: ProvisioningProfileTests.self)))
    }
}

final class SemVerTests: XCTestCase {
    func testOrdering() throws {
        XCTAssertGreaterThan(try XCTUnwrap(SemVer("v0.3.10")), try XCTUnwrap(SemVer("v0.3.9")))
        XCTAssertGreaterThan(try XCTUnwrap(SemVer("1.0")), try XCTUnwrap(SemVer("0.99.99")))
        XCTAssertEqual(SemVer("v0.3.0"), SemVer("0.3.0"))
        XCTAssertEqual(SemVer("v0.3"), SemVer("0.3.0"))
        XCTAssertLessThan(try XCTUnwrap(SemVer("v0.3.1-rc.1")), try XCTUnwrap(SemVer("v0.3.1")))
        XCTAssertLessThan(try XCTUnwrap(SemVer("v0.3.1-rc.2")), try XCTUnwrap(SemVer("v0.3.1-rc.10")))
        XCTAssertNil(SemVer("latest"))
        XCTAssertNil(SemVer("v1.2.3.4"))
        XCTAssertNil(SemVer("v1..2"))
    }

    func testIsNewer() {
        XCTAssertTrue(SemVer.isNewer("v0.3.10", than: "0.3.9"))
        XCTAssertTrue(SemVer.isNewer("v0.3.1", than: "0.3.0"))
        XCTAssertFalse(SemVer.isNewer("v0.3.0", than: "0.3.0"))
        XCTAssertFalse(SemVer.isNewer("v0.2.9", than: "0.3.0"))
        XCTAssertFalse(SemVer.isNewer("v0.4.0-beta.1", than: "0.3.0"), "a pre-release is never offered")
        XCTAssertFalse(SemVer.isNewer(nil, than: "0.3.0"))
    }

    func testHighestReleaseTag() {
        let tags = ["v0.2.9", "v0.3.9", "v0.3.10", "v1.0.0-beta", "design-kit-1.5.0", "0.9.0", "nightly"]
        XCTAssertEqual(SemVer.highestReleaseTag(tags), "v0.3.10")
        XCTAssertNil(SemVer.highestReleaseTag(["nightly", "v2.0.0-rc.1"]))
    }
}

final class BannerTests: XCTestCase {
    private let now = ISO8601DateFormatter().date(from: "2026-10-13T10:00:00Z")!

    func testSignatureWithTwoDaysOrLessShowsTheBanner() {
        let soon = now.addingTimeInterval(2 * 86400 - 60)
        XCTAssertEqual(BannerReason.reasons(expiry: soon, now: now, appVersion: "0.3.0", latest: []),
                       [.signature(daysLeft: 2, expiry: soon)])
        let later = now.addingTimeInterval(3 * 86400)
        XCTAssertEqual(BannerReason.reasons(expiry: later, now: now, appVersion: "0.3.0", latest: []), [])
        XCTAssertEqual(BannerReason.reasons(expiry: nil, now: now, appVersion: "0.3.0", latest: []), [],
                       "an unknown expiry (simulator) shows nothing")
    }

    func testNewerVersionFromGitHubOrTheComputer() {
        XCTAssertEqual(BannerReason.reasons(expiry: nil, now: now, appVersion: "0.3.0", latest: ["v0.3.1", "0.3.2"]),
                       [.newVersion("v0.3.2")])
        XCTAssertEqual(BannerReason.reasons(expiry: nil, now: now, appVersion: "0.3.0", latest: ["v0.3.0", nil]), [])
    }

    func testExpiryReminderIsTheDayBeforeAtTen() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "Australia/Melbourne"))
        let formats = DateFormats(timeZone: calendar.timeZone)
        let expiry = try XCTUnwrap(formats.parseExport("2026-10-20 08:30:00 +1100"))
        let start = try XCTUnwrap(formats.parseExport("2026-10-13 21:00:00 +1100"))
        let when = try XCTUnwrap(Reminders.expiryReminderDate(expiry: expiry, now: start, calendar: calendar))
        XCTAssertEqual(formats.exportString(when), "2026-10-19 10:00:00 +1100")
        let tooLate = try XCTUnwrap(formats.parseExport("2026-10-19 11:00:00 +1100"))
        XCTAssertNil(Reminders.expiryReminderDate(expiry: expiry, now: tooLate, calendar: calendar))
    }
}
