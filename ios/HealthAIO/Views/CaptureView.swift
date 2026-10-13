import SwiftUI

/// What was read, what was sent and when, and what is still waiting.
struct CaptureView: View {
    @Environment(AppModel.self) private var model
    @State private var discarding: OutboxEntry?

    private var sync: SyncEngine { model.sync }

    var body: some View {
        NavigationStack {
            List {
                actions
                lastRead
                lastPackage
                waiting
                computer
                health
                #if DEBUG
                Section("Debug") {
                    Button("Send a sample package") { Task { await sync.sendSample() } }
                        .disabled(sync.isBusy || !model.connection.isPaired)
                }
                #endif
            }
            .dashboardBackground()
            .navigationTitle("Capture")
            .refreshable { await sync.refreshComputer() }
            .task {
                await sync.refreshWaiting()
                await sync.refreshComputer()
            }
            .confirmationDialog("Discard this package?", isPresented: discardPrompt, titleVisibility: .visible,
                                presenting: discarding) { entry in
                Button("Discard", role: .destructive) { Task { await sync.discard(entry.id) } }
            } message: { _ in
                Text("The phone forgets this package. Your next read makes a new one with the same days.")
            }
        }
    }

    // MARK: Sections

    private var actions: some View {
        Section {
            Button {
                Task { await sync.syncNow() }
            } label: {
                Label("Sync now", systemImage: "arrow.triangle.2.circlepath")
            }
            .disabled(sync.isBusy)
            Button {
                Task { await sync.catchUp() }
            } label: {
                Label("Catch up 14 days", systemImage: "calendar.badge.clock")
            }
            .disabled(sync.isBusy)
            if let activity = sync.activity {
                HStack(spacing: 10) {
                    ProgressView()
                    Text(activityText(activity)).foregroundStyle(Theme.ink2)
                }
            }
            if let notice = sync.notice {
                Text(notice).font(.callout).foregroundStyle(Theme.watchInk)
            }
        } footer: {
            Text("The app reads Apple Health and sends it to your computer only while it is open: about a second after you open it, and when you tap Sync now. Nothing goes through a cloud service.")
        }
    }

    private var lastRead: some View {
        Section("Last read") {
            if let read = sync.lastRead {
                LabeledContent("Days", value: dayRange(read.startDate, read.endDate))
                LabeledContent("When", value: read.at.formatted(date: .abbreviated, time: .shortened))
                LabeledContent("Records", value: read.records.formatted())
                LabeledContent("Workouts", value: read.workouts.formatted())
                LabeledContent("Result", value: Strings.readOutcome(read.outcome))
            } else {
                Text("Nothing read yet.").foregroundStyle(Theme.ink3)
            }
        }
    }

    private var lastPackage: some View {
        Section("Last package") {
            if let stored = sync.lastReceipt {
                let receipt = stored.receipt
                LabeledContent("Status", value: Strings.receiptStatus(receipt.status))
                LabeledContent("When", value: stored.at.formatted(date: .abbreviated, time: .shortened))
                if let window = receipt.window, let start = window.startDate, let end = window.endDate {
                    LabeledContent("Days", value: dayRange(start, end))
                }
                ForEach((receipt.rows ?? [:]).sorted(by: { Strings.tableOrder($0.key, $1.key) }), id: \.key) { table, count in
                    LabeledContent(Strings.table(table), value: count.formatted())
                }
            } else {
                Text("No package has reached your computer yet.").foregroundStyle(Theme.ink3)
            }
        }
    }

    private var waiting: some View {
        Section {
            if sync.waiting.isEmpty {
                Text("Nothing waiting.").foregroundStyle(Theme.ink3)
            }
            ForEach(sync.waiting) { entry in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(dayRange(entry.startDate, entry.endDate)).font(.headline)
                        Spacer()
                        Text(Strings.stateTitle(entry.state)).font(.subheadline).foregroundStyle(Theme.watchInk)
                    }
                    Text(entry.message ?? Strings.state(entry.state)).font(.callout).foregroundStyle(Theme.ink2)
                    Text(ByteCountFormatter.string(fromByteCount: Int64(entry.byteCount), countStyle: .file)
                         + " · " + entry.frozenAt.formatted(date: .abbreviated, time: .shortened))
                        .font(.caption).foregroundStyle(Theme.ink3)
                    HStack {
                        if entry.state != .refused {
                            Button("Check and retry") { Task { await sync.checkAndRetry(entry.id) } }
                                .buttonStyle(.bordered)
                                .disabled(sync.isBusy)
                        }
                        Button("Discard this package", role: .destructive) { discarding = entry }
                            .buttonStyle(.bordered)
                    }
                    .padding(.top, 2)
                }
                .padding(.vertical, 4)
            }
        } header: {
            Text("Waiting to send")
        } footer: {
            Text("A package keeps its id and exact contents until your computer confirms it is in your tables. Only one waits at a time.")
        }
    }

    private var computer: some View {
        Section {
            if let status = sync.computer {
                let latest = (status.latest ?? [:]).sorted(by: { Strings.tableOrder($0.key, $1.key) })
                ForEach(latest, id: \.key) { table, day in
                    LabeledContent(Strings.table(table), value: Strings.latestValue(day))
                }
                if let checked = sync.computerCheckedAt {
                    LabeledContent("Checked", value: checked.formatted(date: .omitted, time: .shortened))
                }
            } else if model.connection.isPaired {
                Text("Not checked yet. Pull down to check.").foregroundStyle(Theme.ink3)
            } else {
                Text("Pair with your computer in Settings.").foregroundStyle(Theme.ink3)
            }
        } header: {
            Text("Latest days on your computer")
        }
    }

    private var health: some View {
        Section {
            LabeledContent("Apple Health", value: Strings.healthAccess(sync.healthAccess))
            if sync.healthAccess == .notAsked {
                Button("Allow reading Apple Health") { Task { await sync.requestHealthAccess() } }
            }
        } footer: {
            Text("Read only. To change what Health AIO may read, open the Health app, tap your picture, then Apps.")
        }
    }

    // MARK: Helpers

    private var discardPrompt: Binding<Bool> {
        Binding(get: { discarding != nil }, set: { if !$0 { discarding = nil } })
    }

    private func activityText(_ activity: SyncEngine.Activity) -> String {
        switch activity {
        case .checking: return String(localized: "Asking your computer…")
        case .reading: return String(localized: "Reading Apple Health…")
        case .sending: return String(localized: "Sending to your computer…")
        case .catchingUp(let n, let total): return String(localized: "Catching up: package \(n) of \(total)…")
        }
    }

    private func dayRange(_ start: String, _ end: String) -> String {
        let formats = DateFormats()
        guard let a = formats.parseDay(start), let b = formats.parseDay(end) else { return "\(start) – \(end)" }
        let style = Date.FormatStyle(date: .abbreviated, time: .omitted)
        return start == end ? a.formatted(style) : "\(a.formatted(style)) – \(b.formatted(style))"
    }
}
