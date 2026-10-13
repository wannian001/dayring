import HealthKit

/// The types the app reads and the names and units Apple's export.xml gives them (docs/CAPTURE.md).
enum HealthNames {
    struct QuantitySpec: Sendable {
        let identifier: HKQuantityTypeIdentifier
        /// An HKUnit string that is also the export's `unit` attribute.
        let unit: String
        let isFood: Bool
    }

    static let quantities: [QuantitySpec] = [
        QuantitySpec(identifier: .stepCount, unit: "count", isFood: false),
        QuantitySpec(identifier: .appleExerciseTime, unit: "min", isFood: false),
        QuantitySpec(identifier: .restingHeartRate, unit: "count/min", isFood: false),
        QuantitySpec(identifier: .heartRateVariabilitySDNN, unit: "ms", isFood: false),
        QuantitySpec(identifier: .bodyMass, unit: "kg", isFood: false),
        QuantitySpec(identifier: .activeEnergyBurned, unit: "kcal", isFood: false),
        QuantitySpec(identifier: .basalEnergyBurned, unit: "kcal", isFood: false),
        QuantitySpec(identifier: .dietaryEnergyConsumed, unit: "kcal", isFood: true),
        QuantitySpec(identifier: .dietaryProtein, unit: "g", isFood: true),
        QuantitySpec(identifier: .dietaryCarbohydrates, unit: "g", isFood: true),
        QuantitySpec(identifier: .dietaryFatTotal, unit: "g", isFood: true),
        QuantitySpec(identifier: .dietaryFiber, unit: "g", isFood: true),
    ]

    static let sleepType = HKCategoryType(.sleepAnalysis)

    /// Read permission only. Heart rate is asked for because a workout's average heart rate is hidden without it;
    /// heart-rate samples themselves are never read.
    static var readTypes: Set<HKObjectType> {
        var types = Set<HKObjectType>(quantities.map { HKQuantityType($0.identifier) })
        types.insert(sleepType)
        types.insert(HKObjectType.workoutType())
        types.insert(HKQuantityType(.heartRate))
        return types
    }

    static let metadataKeys = ["HKTimeZone"]
    static let foodMetadataKeys = ["HKTimeZone", "HKFoodType", "HKFoodMeal", "meal"]

    static func sleepValue(_ raw: Int) -> String? {
        switch raw {
        case 0: return "HKCategoryValueSleepAnalysisInBed"
        case 1: return "HKCategoryValueSleepAnalysisAsleepUnspecified"
        case 2: return "HKCategoryValueSleepAnalysisAwake"
        case 3: return "HKCategoryValueSleepAnalysisAsleepCore"
        case 4: return "HKCategoryValueSleepAnalysisAsleepDeep"
        case 5: return "HKCategoryValueSleepAnalysisAsleepREM"
        default: return nil
        }
    }

    static func eventName(_ type: HKWorkoutEventType) -> String? {
        switch type {
        case .pause: return "HKWorkoutEventTypePause"
        case .resume: return "HKWorkoutEventTypeResume"
        case .motionPaused: return "HKWorkoutEventTypeMotionPaused"
        case .motionResumed: return "HKWorkoutEventTypeMotionResumed"
        default: return nil
        }
    }

    static func activityName(_ type: HKWorkoutActivityType) -> String {
        "HKWorkoutActivityType" + (activityNames[type] ?? "Other")
    }

    private static let activityNames: [HKWorkoutActivityType: String] = [
        .americanFootball: "AmericanFootball", .archery: "Archery", .australianFootball: "AustralianFootball",
        .badminton: "Badminton", .baseball: "Baseball", .basketball: "Basketball", .bowling: "Bowling",
        .boxing: "Boxing", .climbing: "Climbing", .cricket: "Cricket", .crossTraining: "CrossTraining",
        .curling: "Curling", .cycling: "Cycling", .elliptical: "Elliptical", .equestrianSports: "EquestrianSports",
        .fencing: "Fencing", .fishing: "Fishing", .functionalStrengthTraining: "FunctionalStrengthTraining",
        .golf: "Golf", .gymnastics: "Gymnastics", .handball: "Handball", .hiking: "Hiking", .hockey: "Hockey",
        .hunting: "Hunting", .lacrosse: "Lacrosse", .martialArts: "MartialArts", .mindAndBody: "MindAndBody",
        .paddleSports: "PaddleSports", .play: "Play", .preparationAndRecovery: "PreparationAndRecovery",
        .racquetball: "Racquetball", .rowing: "Rowing", .rugby: "Rugby", .running: "Running", .sailing: "Sailing",
        .skatingSports: "SkatingSports", .snowSports: "SnowSports", .soccer: "Soccer", .softball: "Softball",
        .squash: "Squash", .stairClimbing: "StairClimbing", .surfingSports: "SurfingSports", .swimming: "Swimming",
        .tableTennis: "TableTennis", .tennis: "Tennis", .trackAndField: "TrackAndField",
        .traditionalStrengthTraining: "TraditionalStrengthTraining", .volleyball: "Volleyball",
        .walking: "Walking", .waterFitness: "WaterFitness", .waterPolo: "WaterPolo", .waterSports: "WaterSports",
        .wrestling: "Wrestling", .yoga: "Yoga", .barre: "Barre", .coreTraining: "CoreTraining",
        .crossCountrySkiing: "CrossCountrySkiing", .downhillSkiing: "DownhillSkiing", .flexibility: "Flexibility",
        .highIntensityIntervalTraining: "HighIntensityIntervalTraining", .jumpRope: "JumpRope",
        .kickboxing: "Kickboxing", .pilates: "Pilates", .snowboarding: "Snowboarding", .stairs: "Stairs",
        .stepTraining: "StepTraining", .wheelchairWalkPace: "WheelchairWalkPace",
        .wheelchairRunPace: "WheelchairRunPace", .taiChi: "TaiChi", .mixedCardio: "MixedCardio",
        .handCycling: "HandCycling", .discSports: "DiscSports", .fitnessGaming: "FitnessGaming",
        .cardioDance: "CardioDance", .socialDance: "SocialDance", .pickleball: "Pickleball",
        .cooldown: "Cooldown", .swimBikeRun: "SwimBikeRun", .transition: "Transition",
        .underwaterDiving: "UnderwaterDiving", .other: "Other",
    ]
}
