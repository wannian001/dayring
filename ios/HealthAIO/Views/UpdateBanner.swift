import SwiftUI

/// On top of every tab when the signature runs out within two days or a newer version exists.
/// Renewing is done by the computer; this banner asks it and follows along.
struct UpdateBanner: View {
    @Environment(AppModel.self) private var model

    private var updates: UpdateCenter { model.updates }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Image(systemName: "arrow.clockwise.circle")
                    .foregroundStyle(Theme.accent)
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(updates.reasons.enumerated()), id: \.offset) { _, reason in
                        Text(Strings.bannerLine(reason)).font(.subheadline.weight(.semibold))
                    }
                    progress
                }
                Spacer(minLength: 0)
            }
            buttons
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface)
        .overlay(alignment: .bottom) { Divider() }
    }

    @ViewBuilder
    private var progress: some View {
        switch updates.renew {
        case .idle:
            Text("Your computer can sign the app again and install it on this phone.")
                .font(.footnote).foregroundStyle(Theme.ink2)
        case .asking:
            Text("Asking your computer…").font(.footnote).foregroundStyle(Theme.ink2)
        case .running(let message):
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Your computer is building and installing the app. iOS will close Health AIO once when the new copy is installed; open it again afterwards.")
            }
            .font(.footnote).foregroundStyle(Theme.ink2)
            if let message, !message.isEmpty {
                Text(message).font(.caption).foregroundStyle(Theme.ink3)
            }
        case .finished(true, let message):
            Text("Renewed.").font(.footnote.weight(.semibold)).foregroundStyle(Theme.goodInk)
            if let message, !message.isEmpty { Text(message).font(.caption).foregroundStyle(Theme.ink3) }
        case .finished(false, let message):
            Text("Renewing did not work.").font(.footnote.weight(.semibold)).foregroundStyle(Theme.offInk)
            if let message, !message.isEmpty { Text(message).font(.caption).foregroundStyle(Theme.ink2) }
            Text(Strings.renewByHand).font(.caption.monospaced()).foregroundStyle(Theme.ink2)
        case .cannot(let reason, _):
            Text(Strings.renewReason(reason)).font(.footnote).foregroundStyle(Theme.ink2)
            Text(Strings.renewByHand).font(.caption.monospaced()).foregroundStyle(Theme.ink2)
        case .failed(let message):
            Text(message).font(.footnote).foregroundStyle(Theme.offInk)
            Text(Strings.renewByHand).font(.caption.monospaced()).foregroundStyle(Theme.ink2)
        }
    }

    @ViewBuilder
    private var buttons: some View {
        let running: Bool = {
            if case .running = updates.renew { return true }
            if case .asking = updates.renew { return true }
            return false
        }()
        HStack(spacing: 12) {
            Button("Renew now") { updates.renewNow(client: model.connection.client()) }
                .prominentButton()
                .disabled(running)
            Button("Not today") { updates.dismissForToday() }
                .buttonStyle(.bordered)
        }
        .controlSize(.small)
    }
}
