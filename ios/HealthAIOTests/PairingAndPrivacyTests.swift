import XCTest
@testable import HealthAIO

final class PairingLinkTests: XCTestCase {
    func testParsesTheLinkHealthaioPairPrints() throws {
        let link = try XCTUnwrap(PairingLink.parse("healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907"))
        XCTAssertEqual(link.serverURL.absoluteString, "http://192.168.1.20:8790")
        XCTAssertEqual(link.code, "48213907")
    }

    func testAcceptsLocalAndTailscaleNames() throws {
        let local = try XCTUnwrap(PairingLink.parse("healthaio://pair?url=http%3A%2F%2Fmac.local%3A8790%2F&code=00000001"))
        XCTAssertEqual(local.serverURL.absoluteString, "http://mac.local:8790")
        XCTAssertNotNil(PairingLink.parse("healthaio://pair?url=http%3A%2F%2F100.101.102.103%3A8790&code=12345678"))
        XCTAssertNotNil(PairingLink.parse("healthaio://pair?url=http%3A%2F%2Fmac.tail1234.ts.net%3A8790&code=12345678"))
    }

    func testRejectsBadLinks() {
        XCTAssertNil(PairingLink.parse("https://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907"))
        XCTAssertNil(PairingLink.parse("healthaio://open?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907"))
        XCTAssertNil(PairingLink.parse("healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=4821390"))
        XCTAssertNil(PairingLink.parse("healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=4821390a"))
        XCTAssertNil(PairingLink.parse("healthaio://pair?code=48213907"))
        XCTAssertNil(PairingLink.parse("healthaio://pair?url=ftp%3A%2F%2F192.168.1.20&code=48213907"))
        XCTAssertNil(PairingLink.parse("healthaio://pair?url=http%3A%2F%2Fevil.example.com%3A8790&code=48213907"),
                     "the server refuses DNS names, so the app does not pair with one")
    }

    func testTypedAddresses() {
        XCTAssertEqual(ServerAddress.normalize("192.168.1.20:8790")?.absoluteString, "http://192.168.1.20:8790")
        XCTAssertEqual(ServerAddress.normalize(" http://192.168.1.20:8790/dashboard?x=1 ")?.absoluteString,
                       "http://192.168.1.20:8790")
        XCTAssertEqual(ServerAddress.normalize("localhost:8790")?.absoluteString, "http://localhost:8790")
        XCTAssertNil(ServerAddress.normalize(""))
        XCTAssertNil(ServerAddress.normalize("999.1.1.1:8790"))
        XCTAssertNil(ServerAddress.normalize("example.com"))
        XCTAssertTrue(ServerAddress.isValidCode("00000000"))
        XCTAssertFalse(ServerAddress.isValidCode("１２３４５６７８"), "full-width digits are not a code")
    }

    func testPanelURLAndOrigin() throws {
        let server = try XCTUnwrap(URL(string: "http://192.168.1.20:8790"))
        XCTAssertEqual(WebPanel.panelURL(server, language: "en").absoluteString, "http://192.168.1.20:8790/?app=1&lang=en#today")
        XCTAssertEqual(WebPanel.panelURL(server, language: "zh-Hans").absoluteString, "http://192.168.1.20:8790/?app=1&lang=zh#today")
        XCTAssertTrue(WebPanel.sameOrigin(try XCTUnwrap(URL(string: "http://192.168.1.20:8790/api/today")), server))
        XCTAssertFalse(WebPanel.sameOrigin(try XCTUnwrap(URL(string: "http://192.168.1.20:8080/")), server))
        XCTAssertFalse(WebPanel.sameOrigin(try XCTUnwrap(URL(string: "https://github.com/")), server))
    }
}

final class SourcePrivacyTests: XCTestCase {
    func testAppleWatchNeverSendsTheDeviceName() {
        let source = SourcePrivacy.source(bundleID: "com.apple.health.81AF1B4C-0000-0000-0000-000000000000",
                                          name: "Sam’s Apple Watch", productType: "Watch7,1", deviceModel: "Watch")
        XCTAssertEqual(source, .init(sourceName: "Apple Watch", device: "Watch"))
    }

    func testIPhoneNeverSendsTheDeviceName() {
        let source = SourcePrivacy.source(bundleID: "com.apple.health.0F3C", name: "Sam's iPhone",
                                          productType: "iPhone17,3", deviceModel: "iPhone")
        XCTAssertEqual(source, .init(sourceName: "iPhone", device: "iPhone"))
        // No product type and no device: still the plain product.
        XCTAssertEqual(SourcePrivacy.source(bundleID: "com.apple.health.X", name: "Sam's iPhone",
                                            productType: nil, deviceModel: nil),
                       .init(sourceName: "iPhone", device: "iPhone"))
    }

    func testThirdPartyAppNamesAreKept() {
        let source = SourcePrivacy.source(bundleID: "com.myfitnesspal.mfp", name: "MyFitnessPal",
                                          productType: "iPhone17,3", deviceModel: "iPhone")
        XCTAssertEqual(source, .init(sourceName: "MyFitnessPal", device: "iPhone"))
    }

    func testHealthAppEntriesKeepTheirPlainName() {
        // Typed into the Health app: bundle "com.apple.Health", name "Health", often no device.
        let source = SourcePrivacy.source(bundleID: "com.apple.Health", name: "Health",
                                          productType: "iPhone17,3", deviceModel: nil)
        XCTAssertEqual(source, .init(sourceName: "Health", device: "iPhone"))
    }

    func testAPersonalDeviceModelIsDropped() {
        let source = SourcePrivacy.source(bundleID: "com.example.scale", name: "Scale App",
                                          productType: nil, deviceModel: "Sam's Scale")
        XCTAssertEqual(source, .init(sourceName: "Scale App", device: nil))
    }

    func testHealthNames() {
        XCTAssertEqual(HealthNames.sleepValue(3), "HKCategoryValueSleepAnalysisAsleepCore")
        XCTAssertEqual(HealthNames.sleepValue(0), "HKCategoryValueSleepAnalysisInBed")
        XCTAssertNil(HealthNames.sleepValue(99))
        XCTAssertEqual(HealthNames.activityName(.running), "HKWorkoutActivityTypeRunning")
        XCTAssertEqual(HealthNames.activityName(.traditionalStrengthTraining),
                       "HKWorkoutActivityTypeTraditionalStrengthTraining")
        XCTAssertEqual(HealthNames.eventName(.pause), "HKWorkoutEventTypePause")
        XCTAssertEqual(HealthNames.eventName(.motionResumed), "HKWorkoutEventTypeMotionResumed")
        XCTAssertNil(HealthNames.eventName(.lap))
        XCTAssertEqual(Set(HealthNames.quantities.map(\.unit)), ["count", "min", "count/min", "ms", "kg", "kcal", "g"])
    }
}
