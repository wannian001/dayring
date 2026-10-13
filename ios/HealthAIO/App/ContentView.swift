import SwiftUI

struct ContentView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        @Bindable var model = model
        @Bindable var reminders = model.reminders
        VStack(spacing: 0) {
            if model.updates.showBanner {
                UpdateBanner()
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
            TabView(selection: $model.tab) {
                PanelView()
                    .tabItem { Label("Panel", systemImage: "circle.circle") }
                    .tag(AppTab.panel)
                CaptureView()
                    .tabItem { Label("Capture", systemImage: "arrow.up.heart") }
                    .tag(AppTab.capture)
                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gearshape") }
                    .tag(AppTab.settings)
            }
        }
        .background(Theme.background)
        .animation(.easeOut(duration: 0.25), value: model.updates.showBanner)
        .onChange(of: scenePhase, initial: true) { _, phase in
            if phase == .active { model.becameActive() }
        }
        .onOpenURL { model.open($0) }
        .alert("Pair with this computer?", isPresented: pairingPrompt, presenting: model.pendingLink) { link in
            Button("Pair") { Task { await model.pair(link) } }
            Button("Cancel", role: .cancel) {}
        } message: { link in
            if model.connection.isPaired {
                Text("Health AIO will send your health data to \(ServerAddress.display(link.serverURL)). This replaces the current pairing.")
            } else {
                Text("Health AIO will send your health data to \(ServerAddress.display(link.serverURL)).")
            }
        }
        .sheet(isPresented: $reminders.showPrimer) {
            NotificationPrimer()
                .presentationDetents([.medium])
        }
        #if DEBUG
        .task { await model.debugLaunchActions() }
        #endif
    }

    private var pairingPrompt: Binding<Bool> {
        Binding(get: { model.pendingLink != nil }, set: { if !$0 { model.pendingLink = nil } })
    }
}
