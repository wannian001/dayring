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
            records.append(HealthReader.record(sample, type: HealthNames.sleepType.identifier, unit: nil,
                                               value: .text(value), source: HealthReader.source(of: sample),
                                               metadataKeys: HealthNames.metadataKeys, formats: formats))
        }

        for spec in HealthNames.quantities {
            let type = HKQuantityType(spec.identifier)
            let samples = try await HKSampleQueryDescriptor(
                predicates: [.quantitySample(type: type, predicate: dayPredicate)],
                sortDescriptors: [SortDescriptor(\.startDate)]
            ).result(for: store)
            records += HealthReader.quantityRecords(samples, spec: spec, formats: formats,
                                                    source: HealthReader.source(of:))
        }

        let workouts = try await HKSampleQueryDescriptor(
            predicates: [.workout(dayPredicate)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        ).result(for: store)
        let workoutRecords = workouts.map { workout($0, formats: formats) }

        return Result(records: records, workouts: workoutRecords, completedAt: Date())
    }

    /// One type's samples as records: the spec's type name and unit string exactly as they are, each value read in
    /// that unit; a sample whose quantity does not fit the unit is skipped. The source is passed in, so the tests can
    /// run this on samples they make themselves, which never went through Apple Health.
    static func quantityRecords(_ samples: [HKQuantitySample], spec: HealthNames.QuantitySpec, formats: DateFormats,
                                source: (HKSample) -> SourcePrivacy.Source) -> [HealthRecord] {
        let unit = spec.hkUnit
        let metadataKeys = spec.isFood ? HealthNames.foodMetadataKeys : HealthNames.metadataKeys
        return samples.compactMap { sample in
            guard sample.quantity.is(compatibleWith: unit) else { return nil }
            return record(sample, type: spec.identifier.rawValue, unit: spec.unit,
                          value: .text(NumberText.string(sample.quantity.doubleValue(for: unit))),
                          source: source(sample), metadataKeys: metadataKeys, formats: formats)
        }
    }

    private static func source(of sample: HKSample) -> SourcePrivacy.Source {
        let revision = sample.sourceRevision
        return SourcePrivacy.source(bundleID: revision.source.bundleIdentifier, name: revision.source.name,
                                    productType: revision.productType, deviceModel: sample.device?.model)
    }

    private static func record(_ sample: HKSample, type: String, unit: String?, value: ExportValue,
                               source: SourcePrivacy.Source, metadataKeys: [String],
                               formats: DateFormats) -> HealthRecord {
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
        let source = HealthReader.source(of: workout)
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
