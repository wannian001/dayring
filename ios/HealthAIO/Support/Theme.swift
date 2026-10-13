import SwiftUI
import UIKit

/// Colours from the dashboard's tokens (healthaio/web/css/tokens.css): graphite neutrals and a blue accent in
/// light mode, dusk neutrals and a violet accent in dark mode, so the native tabs sit well next to the panel.
enum Theme {
    static let background = Color(light: 0xF4F4F3, dark: 0x0B0D13)
    static let surface = Color(light: 0xFFFFFF, dark: 0x141822)
    static let ink2 = Color(light: 0x4A4A48, dark: 0xB4BBCC)
    static let ink3 = Color(light: 0x6A6A67, dark: 0x8C95A8)
    static let accent = Color(light: 0x1F5FBF, dark: 0xAEA2F7)
    /// Text on an accent fill: white on the blue, deep violet on the light violet (--on-accent).
    static let onAccent = Color(light: 0xFFFFFF, dark: 0x14102E)
    static let goodInk = Color(light: 0x1D7A1D, dark: 0x4CC94C)
    static let watchInk = Color(light: 0x8A5A00, dark: 0xF5BD4A)
    static let offInk = Color(light: 0xB42828, dark: 0xF27C7C)

    static let backgroundUI = UIColor(light: 0xF4F4F3, dark: 0x0B0D13)
}

extension UIColor {
    convenience init(light: UInt32, dark: UInt32) {
        self.init { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                           blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
        }
    }
}

extension Color {
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor(light: light, dark: dark))
    }
}

extension View {
    /// The filled button, with the dashboard's text colour on the accent.
    func prominentButton() -> some View {
        buttonStyle(.borderedProminent).foregroundStyle(Theme.onAccent)
    }

    /// The dashboard's page background behind a List or Form, with rows on the surface colour.
    func dashboardBackground() -> some View {
        scrollContentBackground(.hidden).background(Theme.background)
    }
}
