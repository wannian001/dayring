import SwiftUI
import UIKit

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var address = ""
    @State private var code = ""
    @State private var confirmUnpair = false

    var body: some View {
        NavigationStack {
            Form {
                computer
                health
                reminders
                versions
                about
            }
            .dashboardBackground()
            .navigationTitle("Settings")
        }
    }

    // MARK: Computer

    @ViewBuilder
    private var computer: some View {
        if let url = model.connection.serverURL {
            Section {
                LabeledContent("Paired as", value: "\(model.connection.deviceName) · \(ServerAddress.display(url))")
                if let since = model.connection.pairedAt {
                    LabeledContent("Since", value: since.formatted(date: .abbreviated, time: .omitted))
                }
                Button("Unpair", role: .destructive) { confirmUnpair = true }
                    .confirmationDialog("Unpair from this computer?", isPresented: $confirmUnpair,
                                        titleVisibility: .visible) {
                        Button("Unpair", role: .destructive) { Task { await model.unpair() } }
                    } message: {
                        Text("The phone forgets the address and both keys. To cut it off on the computer as well, run healthaio devices revoke there.")
                    }
            } header: {
                Text("Your computer")
            }
        } else {
            Section {
                TextField("Address, e.g. 192.168.1.20:8790", text: $address)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("8-digit code", text: $code)
                    .keyboardType(.numberPad)
                    .onChange(of: code) { _, new in code = String(new.filter(\.isNumber).prefix(8)) }
                Button {
                    pairTyped()
                } label: {
                    if model.isPairing { ProgressView() } else { Text("Pair") }
                }
                .disabled(model.isPairing || address.isEmpty || code.count != 8)
                Button("Paste pairing link") { pasteLink() }
                    .disabled(model.isPairing)
                if let error = model.pairingError {
                    Text(error).font(.callout).foregroundStyle(Theme.offInk)
                }
            } header: {
                Text("Your computer")
            } footer: {
                Text("On your computer run healthaio pair (or Pair iPhone… in the Mac app), then point the iPhone Camera at the QR code. Or type the address and code it shows. The phone must be on the same Wi-Fi or on Tailscale.")
            }
        }
    }

    private func pairTyped() {
        guard let url = ServerAddress.normalize(address), ServerAddress.isValidCode(code) else {
            model.pairingError = PairingError.badInput.localizedDescription
            return
        }
        let link = PairingLink(serverURL: url, code: code)
        Task {
            await model.pair(link)
            if model.connection.isPaired { code = "" }
        }
    }

    private func pasteLink() {
        guard let text = UIPasteboard.general.string, let link = PairingLink.parse(text) else {
            model.pairingError = String(localized: "The clipboard has no pairing link. Copy the healthaio://pair… link your computer printed.")
            return
        }
        model.pendingLink = link
    }

    // MARK: Apple Health

    private var health: some View {
        Section {
            Button("Allow reading Apple Health") { Task { await model.sync.requestHealthAccess() } }
            LabeledContent("Status", value: Strings.healthAccess(model.sync.healthAccess))
        } header: {
            Text("Apple Health")
        } footer: {
            Text("Health AIO only reads. iOS asks once; to change your answer later, open the Health app, tap your picture, then Apps.")
        }
    }

    // MARK: Reminders

    private var reminders: some View {
        Section {
            Toggle("Remind me before the signature runs out", isOn: Binding(
                get: { model.reminders.enabled },
                set: { on in Task { await model.reminders.setEnabled(on, expiry: model.updates.expiry) } }))
            if model.reminders.status == .denied && model.reminders.enabled {
                Text("Notifications are off for Health AIO in iOS Settings.")
                    .font(.callout).foregroundStyle(Theme.watchInk)
                Button("Open iOS Settings") {
                    if let url = URL(string: UIApplication.openNotificationSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
            }
        } header: {
            Text("Reminders")
        } footer: {
            Text("One notification the day before the signature runs out, at 10:00, and one when a new version is out.")
        }
    }

    // MARK: Versions

    private var versions: some View {
        let updates = model.updates
        return Section {
            LabeledContent("This app", value: "\(UpdateCenter.appVersion) (\(UpdateCenter.appBuild))")
            LabeledContent("Signature valid until", value: updates.expiry.map {
                $0.formatted(date: .abbreviated, time: .shortened)
            } ?? String(localized: "Unknown (simulator or store build)"))
            LabeledContent("Latest on GitHub", value: updates.githubLatest ?? "—")
            LabeledContent("Your computer runs", value: updates.computerVersion ?? model.connection.serverVersion ?? "—")
            if let checked = updates.lastCheckedAt {
                LabeledContent("Checked", value: checked.formatted(date: .abbreviated, time: .shortened))
            }
            Button {
                Task { await updates.check(client: model.connection.client(), notify: false) }
            } label: {
                if updates.isChecking { ProgressView() } else { Text("Check now") }
            }
            .disabled(updates.isChecking)
        } header: {
            Text("Version and signature")
        } footer: {
            Text("An app you build yourself runs for 7 days with a free Apple ID, a year with a paid developer account. The app checks once a day and reminds you two days before.")
        }
    }

    // MARK: About

    private var about: some View {
        Section("About") {
            Link("Health AIO on GitHub", destination: GitHubReleases.repository)
            Link("Releases", destination: GitHubReleases.releasesPage)
            Link("How the phone and computer talk", destination: GitHubReleases.protocolDoc)
        }
    }
}
