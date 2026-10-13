import SwiftUI

/// A short explanation shown once before iOS asks for notification permission.
struct NotificationPrimer: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "bell.badge")
                .font(.system(size: 40))
                .foregroundStyle(Theme.accent)
            Text("Reminders before the app stops opening")
                .font(.title3.weight(.semibold))
                .multilineTextAlignment(.center)
            Text("An app you build yourself stops opening when its signature runs out: after 7 days with a free Apple ID. Health AIO reminds you the day before, and when a new version is out. Nothing else.")
                .font(.callout)
                .foregroundStyle(Theme.ink2)
                .multilineTextAlignment(.center)
            VStack(spacing: 10) {
                Button {
                    Task { await model.reminders.primerAccepted() }
                } label: {
                    Text("Allow reminders").frame(maxWidth: .infinity)
                }
                .prominentButton()
                Button("Not now") { model.reminders.primerDeclined() }
            }
            .controlSize(.large)
        }
        .padding(24)
        .frame(maxHeight: .infinity)
        .background(Theme.background)
    }
}
