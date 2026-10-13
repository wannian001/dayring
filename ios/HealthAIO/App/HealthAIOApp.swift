import SwiftUI

@main
struct HealthAIOApp: App {
    /// Unit tests run inside the app; they get a blank window instead of pairing, Health prompts and network checks.
    private static let isTestHost = ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil

    var body: some Scene {
        WindowGroup {
            if HealthAIOApp.isTestHost {
                Color.clear
            } else {
                RootView()
            }
        }
    }
}

private struct RootView: View {
    @State private var model = AppModel()

    var body: some View {
        ContentView()
            .environment(model)
            .tint(Theme.accent)
    }
}
