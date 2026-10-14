#if DEBUG
import Foundation

/// A made-up 3-day package (no Apple Health needed), for screenshots and checks against a test server.
/// The numbers are invented; nothing here comes from a person.
enum SamplePackage {
    static func make(now: Date, deviceID: String, appVersion: String, timeZone: TimeZone = .current) -> CapturePackage {
        let formats = DateFormats(timeZone: timeZone)
        let calendar = DateFormats.gregorian(timeZone)
        let window = CaptureWindow.recent(now: now, timeZone: timeZone)
            ?? CaptureWindow(dayStart: now, endDay: now, sleepStart: now, queryEnd: now, timeZone: timeZone)
        var records: [HealthRecord] = []
        var workouts: [WorkoutRecord] = []

        func at(_ day: Date, _ hour: Int, _ minute: Int = 0) -> Date {
            calendar.date(bySettingHour: hour, minute: minute, second: 0, of: day) ?? day
        }
        func add(_ type: String, _ start: Date, _ end: Date, _ value: String, unit: String?,
                 watch: Bool = true, metadata: [String: String]? = nil) {
            // Only what has already happened: the server keeps rows inside the window, and nothing is from the future.
            guard end <= now else { return }
            records.append(HealthRecord(type: type, sourceName: watch ? "Apple Watch" : "iPhone",
                                        device: watch ? "Watch" : "iPhone", unit: unit,
                                        startDate: formats.exportString(start), endDate: formats.exportString(end),
                                        value: .text(value), metadata: metadata))
        }

        let zone = ["HKTimeZone": timeZone.identifier]
        for offset in 0..<3 {
            guard let day = calendar.date(byAdding: .day, value: offset, to: window.dayStart),
                  let evening = calendar.date(byAdding: .day, value: -1, to: day) else { continue }
            let sleep = "HKCategoryTypeIdentifierSleepAnalysis"
            add(sleep, at(evening, 23, 20 + offset * 5), at(day, 3, 0), "HKCategoryValueSleepAnalysisAsleepCore",
                unit: nil, metadata: zone)
            add(sleep, at(day, 3, 0), at(day, 4, 10), "HKCategoryValueSleepAnalysisAsleepDeep", unit: nil, metadata: zone)
            add(sleep, at(day, 4, 10), at(day, 6, 50), "HKCategoryValueSleepAnalysisAsleepREM", unit: nil, metadata: zone)
            add("HKQuantityTypeIdentifierRestingHeartRate", at(day, 8), at(day, 8), String(57 + offset), unit: "count/min")
            add("HKQuantityTypeIdentifierHeartRateVariabilitySDNN", at(day, 3), at(day, 3, 1), String(46 - offset * 2),
                unit: "ms")
            add("HKQuantityTypeIdentifierStepCount", at(day, 9), at(day, 10), String(4200 + offset * 900), unit: "count")
            add("HKQuantityTypeIdentifierStepCount", at(day, 9), at(day, 10), String(4000 + offset * 850),
                unit: "count", watch: false)
            add("HKQuantityTypeIdentifierAppleExerciseTime", at(day, 7), at(day, 7, 30), "24", unit: "min")
            add("HKQuantityTypeIdentifierActiveEnergyBurned", at(day, 7), at(day, 10), "310", unit: "kcal")
            add("HKQuantityTypeIdentifierBasalEnergyBurned", at(day, 0), at(day, 10), "760", unit: "kcal")
            if offset == 1, at(day, 7, 31) <= now {
                workouts.append(WorkoutRecord(
                    workoutActivityType: "HKWorkoutActivityTypeRunning", duration: .text("28.5"), durationUnit: "min",
                    sourceName: "Apple Watch", device: "Watch",
                    startDate: formats.exportString(at(day, 7)), endDate: formats.exportString(at(day, 7, 31)),
                    events: [WorkoutEvent(type: "HKWorkoutEventTypePause", date: formats.exportString(at(day, 7, 12))),
                             WorkoutEvent(type: "HKWorkoutEventTypeResume", date: formats.exportString(at(day, 7, 14)))],
                    statistics: [WorkoutStatistic(type: "HKQuantityTypeIdentifierActiveEnergyBurned", sum: .text("265"),
                                                  unit: "kcal"),
                                 WorkoutStatistic(type: "HKQuantityTypeIdentifierHeartRate", average: .text("146"),
                                                  unit: "count/min")]))
                // Effort (iOS 18 and later): your rating and the watch's estimate, each spanning the workout.
                add("HKQuantityTypeIdentifierWorkoutEffortScore", at(day, 7), at(day, 7, 31), "6",
                    unit: "appleEffortScore")
                add("HKQuantityTypeIdentifierEstimatedWorkoutEffortScore", at(day, 7), at(day, 7, 31), "7",
                    unit: "appleEffortScore")
                // The watch's VO2 max estimate from the outdoor run, a single moment at its end.
                add("HKQuantityTypeIdentifierVO2Max", at(day, 7, 31), at(day, 7, 31), "41.8",
                    unit: HealthNames.vo2MaxUnit)
            }
        }

        return CapturePackage(
            schema: CapturePackage.schemaName, packageID: "ios-sample-" + UUID().uuidString, kind: "health",
            createdAt: formats.isoString(now), timezone: timeZone.identifier,
            device: PackageDevice(id: deviceID, name: "iPhone", appVersion: appVersion),
            window: window.packageWindow(readCompletedAt: now), records: records, workouts: workouts)
    }
}
#endif
