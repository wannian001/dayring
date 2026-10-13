import Foundation

/// The newest published version of the project. Releases first; a repository with only tags falls back to the
/// highest `v*` tag.
enum GitHubReleases {
    static let repository = URL(string: "https://github.com/wannian001/proactive-health-aio")!
    static let releasesPage = URL(string: "https://github.com/wannian001/proactive-health-aio/releases")!
    static let protocolDoc = URL(string: "https://github.com/wannian001/proactive-health-aio/blob/main/docs/CAPTURE.md")!
    private static let api = "https://api.github.com/repos/wannian001/proactive-health-aio"

    private struct Release: Decodable {
        var tagName: String
        enum CodingKeys: String, CodingKey { case tagName = "tag_name" }
    }

    private struct Tag: Decodable {
        var name: String
    }

    static func latestTag() async -> String? {
        guard let latest = URL(string: "\(api)/releases/latest"), let tags = URL(string: "\(api)/tags?per_page=100")
        else { return nil }
        if let (status, body) = await get(latest) {
            if status == 200, let release = try? JSONDecoder().decode(Release.self, from: body) {
                return release.tagName
            }
            guard status == 404 else { return nil }
        } else {
            return nil
        }
        guard let (status, body) = await get(tags), status == 200,
              let list = try? JSONDecoder().decode([Tag].self, from: body) else { return nil }
        return SemVer.highestReleaseTag(list.map(\.name))
    }

    private static func get(_ url: URL) async -> (Int, Data)? {
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("HealthAIO-iOS", forHTTPHeaderField: "User-Agent")
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return nil }
        return (http.statusCode, data)
    }
}
