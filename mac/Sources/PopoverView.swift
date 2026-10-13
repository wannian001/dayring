import SwiftUI

/// The popover under the menu bar icon: the dashboard server, Screen Time collection, the iPhone and updates.
struct PopoverView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HeaderRow(model: model)
            if let problem = model.setupProblem {
                SetupCard(model: model, problem: problem)
            }
            DashboardCard(model: model)
            ScreenTimeCard(model: model)
            IPhoneCard(model: model)
            UpdatesCard(model: model)
            HStack {
                Button(S.settings) { model.actions?.openSettings() }.aio(.quiet)
                Spacer()
                Button(S.quit) { model.actions?.quit() }.aio(.quiet)
            }
        }
        .padding(12)
        .frame(width: 360, alignment: .leading)
    }
}

private struct HeaderRow: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                RingLogoView().frame(width: 20, height: 20)
                Text("Health AIO").font(.system(size: 14, weight: .semibold)).foregroundColor(Tok.ink)
                Spacer()
                if let v = model.displayVersion {
                    Text(v).font(.system(size: 11).monospacedDigit()).foregroundColor(Tok.ink3)
                }
            }
            if let error = model.statusError, model.setupProblem == nil {
                Text(S.statusFailed + " " + error).font(.system(size: 11)).foregroundColor(Tone.off.ink)
                    .lineLimit(4).fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.horizontal, 4)
        .padding(.bottom, 2)
    }
}

private struct SetupCard: View {
    @ObservedObject var model: AppModel
    let problem: String

    var body: some View {
        Card(icon: "exclamationmark.triangle.fill", tint: Tone.watch.fill, title: S.settings.replacingOccurrences(of: "…", with: "")) {
            Text(problem).font(.system(size: 12.5, weight: .medium)).foregroundColor(Tok.ink)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(S.chooseConfig) { model.actions?.chooseConfig() }.aio(.primary)
            }
        }
    }
}

private struct DashboardCard: View {
    @ObservedObject var model: AppModel

    var body: some View {
        Card(icon: "square.grid.2x2.fill", tint: Tok.accent, title: S.dashboard) {
            HStack(alignment: .center, spacing: 8) {
                StatusLine(tone: model.serverTone, text: model.serverText, detail: model.serverDetail)
                Spacer(minLength: 4)
                Button(S.openDashboard) { model.actions?.openDashboard() }.aio(.primary).disabled(!model.serverUp)
            }
        }
    }
}

private struct ScreenTimeCard: View {
    @ObservedObject var model: AppModel

    var body: some View {
        Card(icon: "hourglass", tint: Tok.focus, title: S.screenTime) {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 3) {
                    lastRun
                    if let next = model.nextCollect, !model.collecting {
                        Text(S.nextRun(TimeText.until(next, now: model.now), every: model.collectEveryHours))
                            .font(.system(size: 11)).foregroundColor(Tok.ink3)
                    }
                }
                Spacer(minLength: 4)
                Button(S.collectNow) { model.actions?.collectNow() }.aio()
                    .disabled(model.collecting || model.setupProblem != nil || model.updating)
            }
            if let result = model.collect, !model.collecting, !result.sources.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(result.sources) { SourceRow(source: $0) }
                }
                .padding(.leading, 14)
            }
            if let error = model.collectError, !model.collecting {
                Text(error).font(.system(size: 11)).foregroundColor(Tone.off.ink).lineLimit(5)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Divider().overlay(Tok.line)
            fullDiskAccess
        }
    }

    @ViewBuilder private var lastRun: some View {
        if model.collecting {
            StatusLine(tone: .busy, text: S.collecting)
        } else if let result = model.collect {
            let when = result.at.map { TimeText.moment($0, now: model.now) } ?? "?"
            StatusLine(tone: result.ok ? .good : .watch, text: S.lastRun(when) + " · " + (result.ok ? S.allRead : S.someFailed))
        } else {
            StatusLine(tone: .neutral, text: S.notCollectedYet)
        }
    }

    @ViewBuilder private var fullDiskAccess: some View {
        switch model.fda {
        case .granted:
            HStack(spacing: 6) {
                Image(systemName: "checkmark.shield.fill").font(.system(size: 11)).foregroundColor(Tone.good.fill)
                Text(S.fdaOn).font(.system(size: 11.5)).foregroundColor(Tok.ink3)
            }
        case .denied:
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Image(systemName: "exclamationmark.shield.fill").font(.system(size: 11)).foregroundColor(Tone.watch.fill)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(S.fdaOff).font(.system(size: 12, weight: .medium)).foregroundColor(Tone.watch.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        Text(S.fdaHow).font(.system(size: 11.5)).foregroundColor(Tok.ink2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                HStack {
                    Spacer()
                    Button(S.openPrivacy) { model.actions?.openPrivacySettings() }.aio(.primary)
                }
            }
            .padding(8)
            .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Tok.watchSoft))
        case .unknown:
            Text(S.fdaUnknown).font(.system(size: 11.5)).foregroundColor(Tok.ink3)
        }
    }
}

private struct SourceRow: View {
    let source: CollectResult.Source

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Image(systemName: source.ok ? "checkmark" : "exclamationmark.triangle.fill")
                .font(.system(size: 9.5, weight: .bold))
                .foregroundColor(source.ok ? Tone.good.ink : Tone.watch.fill)
                .frame(width: 10)
            Text(S.sourceName(source.name)).font(.system(size: 11.5, weight: .medium)).foregroundColor(Tok.ink2)
            if !source.message.isEmpty {
                Text(source.message).font(.system(size: 11)).foregroundColor(source.ok ? Tok.ink3 : Tone.watch.ink)
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct IPhoneCard: View {
    @ObservedObject var model: AppModel

    var body: some View {
        Card(icon: "iphone", tint: Tok.sleep, title: S.iphone) {
            if model.devices.isEmpty {
                Text(S.noPhone).font(.system(size: 12.5)).foregroundColor(Tok.ink2)
            } else {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(model.devices.prefix(3)) { device in
                        HStack(spacing: 4) {
                            Text(device.name).font(.system(size: 12.5, weight: .medium)).foregroundColor(Tok.ink)
                            Text("· " + (device.lastSeen.map { S.lastSeen(TimeText.ago($0, now: model.now)) } ?? S.notSeenYet))
                                .font(.system(size: 11.5)).foregroundColor(Tok.ink3)
                        }
                    }
                }
            }
            signature
            if let reason = model.renewBlockedReason {
                Text(reason).font(.system(size: 11)).foregroundColor(Tok.ink3).fixedSize(horizontal: false, vertical: true)
            }
            if let error = model.renewError, !model.renewBusy {
                Text(error).font(.system(size: 11)).foregroundColor(Tone.off.ink).lineLimit(5)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Button(S.pair) { model.actions?.pairIPhone() }.aio(model.devices.isEmpty ? .primary : .secondary)
                    .disabled(model.setupProblem != nil)
                Spacer()
                Button(S.renew) { model.actions?.renewIPhone() }.aio(model.needsRenew ? .primary : .secondary)
                    .disabled(!model.canRenew)
            }
        }
    }

    @ViewBuilder private var signature: some View {
        if model.renewBusy {
            StatusLine(tone: .busy, text: S.renewing)
        } else if let expiry = model.signatureExpiry {
            if model.signatureExpired {
                StatusLine(tone: .off, text: S.signatureGone, detail: TimeText.day(expiry))
            } else {
                StatusLine(tone: model.needsRenew ? .watch : .good,
                           text: S.signatureLeft(TimeText.remaining(expiry, now: model.now)),
                           detail: TimeText.day(expiry) + " " + TimeText.clock(expiry))
            }
        } else if model.iphone != nil {
            StatusLine(tone: .neutral, text: S.notInstalledHere)
        }
    }
}

private struct UpdatesCard: View {
    @ObservedObject var model: AppModel

    var body: some View {
        Card(icon: "arrow.triangle.2.circlepath", tint: Tok.comms, title: S.updates) {
            HStack(alignment: .center, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    if let v = model.displayVersion {
                        Text(S.version(v)).font(.system(size: 12.5, weight: .medium)).foregroundColor(Tok.ink)
                    }
                    state
                }
                Spacer(minLength: 4)
                if model.updateAvailable && !model.updating {
                    Button(S.updateButton) { model.actions?.installUpdate() }.aio(.primary)
                        .disabled(model.renewBusy || model.checkingUpdate)
                }
                Button(S.checkForUpdates) { model.actions?.checkForUpdates() }.aio()
                    .disabled(model.checkingUpdate || model.updating || model.setupProblem != nil)
            }
            if let error = model.updateError, !model.checkingUpdate {
                Text(error).font(.system(size: 11)).foregroundColor(Tone.off.ink).lineLimit(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    @ViewBuilder private var state: some View {
        if model.updating {
            StatusLine(tone: .busy, text: S.updatingNow)
        } else if model.checkingUpdate {
            StatusLine(tone: .busy, text: S.checking)
        } else if let info = model.update, info.available, let latest = info.latest {
            StatusLine(tone: .watch, text: latest == model.skippedVersion ? S.skipped(latest) : S.available(latest))
        } else if let info = model.update, info.latest != nil {
            Text(S.upToDate(info.checkedAt.map { TimeText.moment($0, now: model.now) })).font(.system(size: 11))
                .foregroundColor(Tok.ink3)
        } else if let reason = model.update?.reason {
            Text(reason).font(.system(size: 11)).foregroundColor(Tok.ink3).lineLimit(2)
        }
    }
}
