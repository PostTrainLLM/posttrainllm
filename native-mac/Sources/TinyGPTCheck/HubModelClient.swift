import Foundation
import TinyGPTData
import TinyGPTIO

/// Read-only Hugging Face **model** Hub client for model-check.
///
/// Fetches exactly two kinds of thing, and nothing larger:
///   1. `GET /api/models/<id>?blobs=true` — repo metadata, sibling file
///      manifest with sizes, tags, pipeline_tag, library_name, gated
///      state, and safetensors parameter statistics.
///   2. Small config files via `/<id>/resolve/<rev>/<path>` — config.json
///      (and callers may ask for other small JSON) capped at 512 KB.
///
/// Weight files are NEVER fetched — the boundary is metadata only.
/// Auth: `HF_TOKEN` env, forwarded by `HFDatasets.httpGet` as a Bearer
/// token; the token is never copied into reports or prompts.
public enum HubModelClient {

    public enum HubError: Error, CustomStringConvertible {
        case notFound(id: String)
        case needsAuth(id: String, gated: Bool)
        case http(status: Int, detail: String)
        case network(String)
        case malformed(String)

        public var description: String {
            switch self {
            case .notFound(let id):
                return "model '\(id)' not found on Hugging Face (or inaccessible)"
            case .needsAuth(let id, let gated):
                return "model '\(id)' requires authentication\(gated ? " (gated repo — accept its license on huggingface.co)" : "") — set HF_TOKEN"
            case .http(let s, let d): return "HF API HTTP \(s): \(d)"
            case .network(let s): return "network error reaching huggingface.co: \(s)"
            case .malformed(let s): return "malformed HF response: \(s)"
            }
        }
    }

    public struct Sibling: Equatable, Sendable {
        public let name: String
        public let size: Int64?         // bytes, when `blobs=true` reports it
        public init(name: String, size: Int64? = nil) {
            self.name = name; self.size = size
        }
    }

    /// Decoded `/api/models/<id>` response — permissive parse, HF adds
    /// fields freely and we only read what we need.
    public struct Info: Sendable {
        public var id: String
        public var sha: String?
        public var lastModified: String?
        public var tags: [String]
        public var pipelineTag: String?
        public var libraryName: String?
        public var gated: Bool
        public var gatedKind: String?       // "auto" | "manual"
        public var isPrivate: Bool
        public var siblings: [Sibling]
        /// safetensors stats: dtype string → parameter count, when the
        /// Hub computed them. e.g. ["BF16": 4_020_000_000]
        public var safetensorsParams: [String: Int64]

        public init(id: String, sha: String? = nil, lastModified: String? = nil,
                    tags: [String] = [], pipelineTag: String? = nil,
                    libraryName: String? = nil, gated: Bool = false,
                    gatedKind: String? = nil, isPrivate: Bool = false,
                    siblings: [Sibling] = [], safetensorsParams: [String: Int64] = [:]) {
            self.id = id; self.sha = sha; self.lastModified = lastModified
            self.tags = tags; self.pipelineTag = pipelineTag
            self.libraryName = libraryName; self.gated = gated
            self.gatedKind = gatedKind; self.isPrivate = isPrivate
            self.siblings = siblings; self.safetensorsParams = safetensorsParams
        }

        public func sibling(named name: String) -> Sibling? {
            siblings.first { $0.name == name }
        }
        public func siblings(matchingSuffix suffix: String) -> [Sibling] {
            siblings.filter { $0.name.lowercased().hasSuffix(suffix) }
        }
        /// Sum of sibling sizes for files with the given suffix.
        public func sizeOf(_ suffix: String) -> Int64 {
            siblings(matchingSuffix: suffix).compactMap(\.size).reduce(0, +)
        }
    }

    /// `GET /api/models/<id>?blobs=true[&revision=<rev>]`.
    public static func info(id: String, revision: String) throws -> Info {
        var url = "https://huggingface.co/api/models/\(id)?blobs=true"
        if revision != "main", let enc = revision.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) {
            url += "&revision=\(enc)"
        }
        let (data, status): (Data, Int)
        do { (data, status) = try HFDatasets.httpGet(url) }
        catch { throw HubError.network("\(error)") }

        switch status {
        case 200: break
        case 404: throw HubError.notFound(id: id)
        case 401, 403: throw HubError.needsAuth(id: id, gated: false)
        default:
            throw HubError.http(status: status,
                                detail: String(data: data.prefix(300), encoding: .utf8) ?? "")
        }
        return try decodeInfo(data: data, fallbackId: id)
    }

    /// Fetch a small config file (`config.json`, `model_index.json`, …).
    /// Returns nil on 404; throws on auth/network failures. Bodies larger
    /// than `maxBytes` are rejected — this client exists to read metadata,
    /// not weights.
    public static func smallFile(id: String, revision: String, path: String,
                                 maxBytes: Int = 512 * 1024) throws -> Data? {
        let encoded = path.split(separator: "/", omittingEmptySubsequences: false)
            .map { String($0).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? String($0) }
            .joined(separator: "/")
        let url = "https://huggingface.co/\(id)/resolve/\(revision)/\(encoded)"
        let (data, status): (Data, Int)
        do { (data, status) = try HFDatasets.httpGet(url) }
        catch { throw HubError.network("\(error)") }
        switch status {
        case 200:
            guard data.count <= maxBytes else {
                throw HubError.malformed("\(path) is \(data.count) bytes — over the \(maxBytes)-byte small-file cap")
            }
            return data
        case 404: return nil
        case 401, 403: throw HubError.needsAuth(id: id, gated: true)
        default:
            throw HubError.http(status: status,
                                detail: String(data: data.prefix(300), encoding: .utf8) ?? "")
        }
    }

    // MARK: - decode

    static func decodeInfo(data: Data, fallbackId: String) throws -> Info {
        let obj: [String: Any]
        do {
            obj = (try JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        } catch { throw HubError.malformed("\(error)") }
        guard !obj.isEmpty else { throw HubError.malformed("empty object") }

        var info = Info(
            id: (obj["id"] as? String) ?? fallbackId,
            sha: obj["sha"] as? String,
            lastModified: obj["lastModified"] as? String,
            tags: (obj["tags"] as? [String]) ?? [],
            pipelineTag: obj["pipeline_tag"] as? String,
            libraryName: obj["library_name"] as? String,
            gated: false,
            gatedKind: nil,
            isPrivate: (obj["private"] as? Bool) ?? false,
            siblings: [],
            safetensorsParams: [:])

        if let g = obj["gated"] as? Bool { info.gated = g }
        if let g = obj["gated"] as? String, g != "false" {
            info.gated = true; info.gatedKind = g
        }
        if let disabled = obj["disabled"] as? Bool, disabled {
            info.tags.append("disabled")
        }

        for sib in (obj["siblings"] as? [[String: Any]] ?? []) {
            guard let name = sib["rfilename"] as? String else { continue }
            let size = (sib["size"] as? NSNumber)?.int64Value
            info.siblings.append(Sibling(name: name, size: size))
        }

        // safetensors stats: {"parameters": {"BF16": 4020000064, ...}, "total": ...}
        if let st = obj["safetensors"] as? [String: Any],
           let params = st["parameters"] as? [String: Any] {
            for (dtype, count) in params {
                if let n = (count as? NSNumber)?.int64Value {
                    info.safetensorsParams[dtype] = n
                }
            }
        }
        return info
    }
}
