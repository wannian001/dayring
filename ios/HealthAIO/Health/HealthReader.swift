import Foundation
import HealthKit

/// Reads Apple Health (read only) and writes records with export.xml's attribute names, units and date format.
struct HealthReader: Sendable {
    let store: HKHealthStore

    init(store: HKHealthStore = HKHealthStore()) {
        self.store = store
    }

    static var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// HealthKit never tells an app whether reading was allowed, only whether it has already asked.
    enum Access: Sendable {
        case unavailable, notAsked, asked
    }

    func access() async -> Access {
        guard HealthReader.isAvailable else { return .unavailable }
        let status = try? await store.statusForAuthorizationRequest(toShare: [], read: HealthNames.readTypes)
        return status == .shouldRequest ? .notAsked : .asked
    }

    func requestAccess() async throws {
        try await store.requestAuthorization(toShare: [], read: HealthNames.readTypes)
    }

    struct Result: Sendable {
        var records: [HealthRecord]
        var workouts: [WorkoutRecord]
        var completedAt: Date
    }

    /// Reads one window. Each type uses a strict start date: sleep from 18:00 the evening before, the rest from
    /// `start_date` 00:00, both up to `queryEnd`. Runs off the main actor.
    @concurrent
    func read(_ window: CaptureWindow) async throws -> Result {
        let formats = DateFormats(timeZone: window.timeZone)
        let dayPredicate = HKQuery.predicateForSamples(withStart: window.dayStart, end: window.queryEnd,
                                                       options: .strictStartDate)
        let sleepPredicate = HKQuery.predicateForSamples(withStart: window.sleepStart, end: window.queryEnd,
                                                         options: .strictStartDate)
        var records: [HealthRecord] = []

        let sleep = try await HKSampleQueryDescriptor(
            predicates: [.categorySample(type: HealthNames.sleepType, predicate: sleepPredicate)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        ).result(for: store)
        for sample in sleep {
            guard let value = HealthNames.sleepValue(sample.value) else { continue }
            records.append(record(sample, type: HealthNames.sleepType.identifier, unit: nil,
                                  value: .text(value), metadataKeys: HealthNames.metadataKeys, formats: formats))
        }

        for spec in HealthNames.quantities {
            let type = HKQuantityType(spec.identifier)
            let unit = HKUnit(from: spec.unit)
            let samples = try await HKSampleQueryDescriptor(
                predicates: [.quantitySample(type: type, predicate: dayPredicate)],
                sortDescriptors: [SortDescriptor(\.startDate)]
            ).result(for: store)
            for sample in samples where sample.quantity.is(compatibleWith: unit) {
                let number = sample.quantity.doubleValue(for: unit)
                records.append(record(sample, type: spec.identifier.rawValue, unit: spec.unit,
                                      value: .text(NumberText.string(number)),
                                      metadataKeys: spec.isFood ? HealthNames.foodMetadataKeys : HealthNames.metadataKeys,
                                      formats: formats))
            }
        }

        let workouts = try await HKSampleQueryDescriptor(
            predicates: [.workout(dayPredicate)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        ).result(for: store)
        let workoutRecords = workouts.map { workout($0, formats: formats) }

        return Result(records: records, workouts: workoutRecords, completedAt: Date())
    }

    private func source(of sample: HKSample) -> SourcePrivacy.Source {
        let revision = sample.sourceRevision
        return SourcePrivacy.source(bundleID: revision.source.bundleIdentifier, name: revision.source.name,
                                    productType: revision.productType, deviceModel: sample.device?.model)
    }

    private func record(_ sample: HKSample, type: String, unit: String?, value: ExportValue,
                        metadataKeys: [String], formats: DateFormats) -> HealthRecord {
        let source = source(of: sample)
        var metadata: [String: String] = [:]
        for key in metadataKeys {
            if let text = sample.metadata?[key] as? String, !text.isEmpty { metadata[key] = text }
        }
        return HealthRecord(type: type, sourceName: source.sourceName, device: source.device, unit: unit,
                            startDate: formats.exportString(sample.startDate),
                            endDate: formats.exportString(sample.endDate),
                            value: value, metadata: metadata.isEmpty ? nil : metadata)
    }

    private func workout(_ workout: HKWorkout, formats: DateFormats) -> WorkoutRecord {
        let source = source(of: workout)
        let events = (workout.workoutEvents ?? []).compactMap { event -> WorkoutEvent? in
            guard let name = HealthNames.eventName(event.type) else { return nil }
            return WorkoutEvent(type: name, date: formats.exportString(event.dateInterval.start))
        }
        var statistics: [WorkoutStatistic] = []
        let energyType = HKQuantityType(.activeEnergyBurned)
        if let sum = workout.statistics(for: energyType)?.sumQuantity() {
            statistics.append(WorkoutStatistic(type: energyType.identifier,
                                               sum: .text(NumberText.string(sum.doubleValue(for: .kilocalorie()))),
                                               unit: "kcal"))
        }
        let heartType = HKQuantityType(.heartRate)
        if let average = workout.statistics(for: heartType)?.averageQuantity() {
            let perMinute = HKUnit.count().unitDivided(by: .minute())
            statistics.append(WorkoutStatistic(type: heartType.identifier,
                                               average: .text(NumberText.string(average.doubleValue(for: perMinute))),
                                               unit: "count/min"))
        }
        return WorkoutRecord(workoutActivityType: HealthNames.activityName(workout.workoutActivityType),
                             duration: .text(NumberText.string(workout.duration / 60)), durationUnit: "min",
                             sourceName: source.sourceName, device: source.device,
                             startDate: formats.exportString(workout.startDate),
                             endDate: formats.exportString(workout.endDate),
                             events: events.isEmpty ? nil : events,
                             statistics: statistics.isEmpty ? nil : statistics)
    }
}
