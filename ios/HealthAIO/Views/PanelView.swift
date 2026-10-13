import SwiftUI
import WebKit

/// The dashboard served by the user's computer, in a web view. Sync work never touches this tab, so it stays
/// usable while the app is reading or sending.
struct PanelView: View {
    @Environment(AppModel.self) private var model
    @State private var state: WebPanel.LoadState = .loading
    @State private var reloads = 0

    var body: some View {
        Group {
            if let url = model.connection.serverURL {
                ZStack {
                    WebPanel(serverURL: url, generation: model.connection.generation, reloads: reloads,
                             readToken: { model.connection.readToken() }, state: $state)
                        .ignoresSafeArea(edges: .bottom)
                    overlay
                }
            } else {
                notPaired
            }
        }
        .background(Theme.background)
    }

    @ViewBuilder
    private var overlay: some View {
        switch state {
        case .loading:
            ProgressView()
        case .loaded:
            EmptyView()
        case .unreachable:
            unavailable(title: "Can't reach your computer", systemImage: "wifi.exclamationmark",
                        text: "Is the phone on the same Wi-Fi as your computer, or on Tailscale? Is healthaio serve --lan running there?")
        case .refused:
            unavailable(title: "Your computer did not let this phone in", systemImage: "lock",
                        text: "The pairing may have been revoked. Pair again in Settings.")
        }
    }

    private func unavailable(title: LocalizedStringKey, systemImage: String, text: LocalizedStringKey) -> some View {
        ContentUnavailableView {
            Label(title, systemImage: systemImage)
        } description: {
            Text(text)
        } actions: {
            Button("Try again") { reloads += 1 }
                .prominentButton()
            if state == .refused {
                Button("Open Settings") { model.tab = .settings }
            }
        }
        .background(Theme.background)
    }

    private var notPaired: some View {
        ContentUnavailableView {
            Label("Not paired yet", systemImage: "link")
        } description: {
            Text("Pair this phone with your computer to see your dashboard here.")
        } actions: {
            Button("Open Settings") { model.tab = .settings }
                .prominentButton()
        }
    }
}

/// A WKWebView that keeps to the paired computer: same host stays inside, other https links open in Safari,
/// anything else is blocked. The read token is set as a cookie before the first load.
struct WebPanel: UIViewRepresentable {
    enum LoadState: Equatable {
        case loading, loaded, unreachable, refused
    }

    let serverURL: URL
    let generation: Int
    let reloads: Int
    let readToken: @MainActor () -> String?
    @Binding var state: LoadState

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.isOpaque = false
        webView.backgroundColor = Theme.backgroundUI
        webView.scrollView.backgroundColor = Theme.backgroundUI
        let refresh = UIRefreshControl()
        refresh.addTarget(context.coordinator, action: #selector(Coordinator.pulled(_:)), for: .valueChanged)
        webView.scrollView.refreshControl = refresh
        context.coordinator.webView = webView
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.parent = self
        let key = "\(serverURL.absoluteString)#\(generation)#\(reloads)"
        if context.coordinator.loadedKey != key {
            context.coordinator.loadedKey = key
            context.coordinator.load(webView)
        }
    }

    /// The page keeps its own language choice; in the app it follows the app's language instead.
    static func panelURL(_ server: URL, language: String? = Bundle.main.preferredLocalizations.first) -> URL {
        var parts = URLComponents(url: server, resolvingAgainstBaseURL: false) ?? URLComponents()
        parts.path = "/"
        let lang = (language ?? "en").lowercased().hasPrefix("zh") ? "zh" : "en"
        parts.queryItems = [URLQueryItem(name: "app", value: "1"), URLQueryItem(name: "lang", value: lang)]
        parts.fragment = "today"
        return parts.url ?? server
    }

    static func sameOrigin(_ url: URL, _ server: URL) -> Bool {
        url.scheme?.lowercased() == server.scheme?.lowercased()
            && url.host()?.lowercased() == server.host()?.lowercased()
            && (url.port ?? defaultPort(url)) == (server.port ?? defaultPort(server))
    }

    private static func defaultPort(_ url: URL) -> Int {
        url.scheme?.lowercased() == "https" ? 443 : 80
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: WebPanel
        var loadedKey: String?
        weak var webView: WKWebView?

        init(_ parent: WebPanel) {
            self.parent = parent
        }

        func load(_ webView: WKWebView) {
            setState(.loading)
            let server = parent.serverURL
            let token = parent.readToken()
            Task {
                if let token, let cookie = PanelCookie.make(token: token, for: server) {
                    await WKWebsiteDataStore.default().httpCookieStore.setCookie(cookie)
                }
                webView.load(URLRequest(url: WebPanel.panelURL(server)))
            }
        }

        @objc func pulled(_ control: UIRefreshControl) {
            guard let webView else {
                control.endRefreshing()
                return
            }
            if webView.url == nil || parent.state != .loaded {
                load(webView)
            } else {
                webView.reload()
            }
        }

        private func setState(_ state: LoadState) {
            if parent.state != state { parent.state = state }
        }

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     preferences: WKWebpagePreferences) async -> (WKNavigationActionPolicy, WKWebpagePreferences) {
            guard let url = action.request.url else { return (.cancel, preferences) }
            if WebPanel.sameOrigin(url, parent.serverURL) { return (.allow, preferences) }
            let isMainFrame = action.targetFrame?.isMainFrame ?? true
            if !isMainFrame, url.scheme == "about" { return (.allow, preferences) }
            if url.scheme?.lowercased() == "https", isMainFrame {
                await UIApplication.shared.open(url)
            }
            return (.cancel, preferences)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse) async
            -> WKNavigationResponsePolicy {
            if response.isForMainFrame, let http = response.response as? HTTPURLResponse,
               http.statusCode == 401 || http.statusCode == 403 {
                setState(.refused)
                return .cancel
            }
            return .allow
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            webView.scrollView.refreshControl?.endRefreshing()
            setState(.loaded)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
                     withError error: Error) {
            webView.scrollView.refreshControl?.endRefreshing()
            if (error as NSError).code == NSURLErrorCancelled { return }
            if parent.state != .refused { setState(.unreachable) }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            webView.scrollView.refreshControl?.endRefreshing()
        }

        /// `target="_blank"` and `window.open`: same rules, but never a second web view.
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = action.request.url {
                if WebPanel.sameOrigin(url, parent.serverURL) {
                    webView.load(action.request)
                } else if url.scheme?.lowercased() == "https" {
                    UIApplication.shared.open(url)
                }
            }
            return nil
        }
    }
}
