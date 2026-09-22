import Foundation
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
/// Auth: `HF_TOKEN` is forwarded as a Bearer token; the token is never
/// copied into reports or prompts.
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
    /// (Not Sendable: `apiConfig` is untyped JSON.)
    public struct Info {
        public var id: String
        public var sha: String? = nil
        public var lastModified: String? = nil
        public var tags: [String] = []
        public var pipelineTag: String? = nil
        public var libraryName: String? = nil
        public var gated = false
        public var gatedKind: String? = nil       // "auto" | "manual"
        public var isPrivate = false
        public var siblings: [Sibling] = []
        /// safetensors stats: dtype string → parameter count, when the
        /// Hub computed them. e.g. ["BF16": 4_020_000_000]
        public var safetensorsParams: [String: Int64] = [:]
        /// The Hub embeds the repo's parsed config.json in the API
        /// response — including for gated repos, where the resolve URL
        /// 401s without a token. This is the single biggest source of
        /// otherwise-unnecessary `unknown` verdicts on popular models.
        public var apiConfig: [String: Any]? = nil
        /// transformersInfo.auto_model — e.g. "AutoModelForCausalLM",
        /// "AutoModelForMaskedLM". Task truth straight from the Hub.
        public var autoModel: String? = nil
        /// transformersInfo.custom_class — set when the repo ships its
        /// own modeling code (trust_remote_code territory).
        public var customClass: String? = nil
        /// cardData.base_model — set on fine-tunes/adapters.
        public var baseModel: String? = nil

        public init(id: String) {
            self.id = id
        }

        public func sibling(named name: String) -> Sibling? {
            siblings.first { $0.name == name }
        }
        public func siblings(matchingSuffix suffix: String) -> [Sibling] {
            siblings.filter { $0.name.lowercased().hasSuffix(suffix) }
        }
        /// Sum of sibling sizes for files with the given suffix.
        public func sizeOf(_ suffix: String) -> Int64 {
            var total: Int64 = 0
            for size in siblings(matchingSuffix: suffix).compactMap(\.size) where size >= 0 {
                let next = total.addingReportingOverflow(size)
                if next.overflow { return Int64.max }
                total = next.partialValue
            }
            return total
        }
    }

    /// `GET /api/models/<id>?blobs=true[&revision=<rev>]`.
    public static func info(id: String, revision: String) throws -> Info {
        var url = "https://huggingface.co/api/models/\(id)?blobs=true"
        if revision != "main", let enc = revision.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) {
            url += "&revision=\(enc)"
        }
        guard let endpoint = URL(string: url) else {
            throw HubError.malformed("invalid model-info request")
        }
        let result = fetch(
            authorizedRequest(url: endpoint), maxBytes: 16 * 1024 * 1024)
        if result.tooLarge {
            throw HubError.malformed("model metadata exceeds the 16 MB API cap")
        }
        if let error = result.error { throw HubError.network("\(error)") }
        let data = result.data
        let status = result.statusCode

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
        guard maxBytes >= 0,
              let url = resolveURL(id: id, revision: revision, path: path) else {
            throw HubError.malformed("invalid small-file request")
        }
        var request = authorizedRequest(url: url)
        request.httpMethod = "GET"
        let result = fetch(request, maxBytes: maxBytes)
        if result.tooLarge {
            throw HubError.malformed("\(path) exceeds the \(maxBytes)-byte small-file cap")
        }
        if let error = result.error { throw HubError.network("\(error)") }
        let data = result.data
        let status = result.statusCode
        switch status {
        case 200:
            return data
        case 404: return nil
        case 401, 403: throw HubError.needsAuth(id: id, gated: true)
        default:
            throw HubError.http(status: status,
                                detail: String(data: data.prefix(300), encoding: .utf8) ?? "")
        }
    }

    /// Fetch the checkpoint's tensor names — the structural evidence for
    /// layout compatibility — without touching weight bytes.
    ///
    /// Two sources, cheapest first:
    ///   1. `model.safetensors.index.json` — sharded repos carry a small
    ///      JSON manifest (`{"weight_map": {name: shard}}`) listing every
    ///      tensor. Bounded at 8 MB.
    ///   2. Range-read the safetensors JSON header of the first weight
    ///      file: `[8-byte LE len][JSON header][weights…]` — the header
    ///      is metadata; a `Range:` GET of its front bytes is not a
    ///      weight download.
    ///
    /// Returns nil when neither source is available/readable — callers
    /// record that as a limitation, never as invented compatibility.
    /// `entries` is the full `{name: {dtype, shape}}` header when the
    /// safetensors header was read (nil for index.json, which is
    /// name→file only) — enough for exact weight-byte/param counts.
    public static func tensorNames(id: String, revision: String,
                                   info: Info) throws -> (names: [String], entries: [String: [String: Any]]?)? {
        if info.sibling(named: "model.safetensors.index.json") != nil {
            if let data = try smallFile(id: id, revision: revision,
                                        path: "model.safetensors.index.json",
                                        maxBytes: 8 * 1024 * 1024),
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let weightMap = obj["weight_map"] as? [String: Any] {
                return (Array(weightMap.keys), nil)
            }
        }
        guard let shard = info.siblings(matchingSuffix: ".safetensors")
            .sorted(by: { $0.name < $1.name }).first else { return nil }
        guard let header = try safetensorsHeader(id: id, revision: revision, path: shard.name)
        else { return nil }
        return (header.keys.filter { $0 != "__metadata__" }.sorted(), header)
    }

    /// Read a safetensors file's JSON header via HTTP Range requests.
    /// Two fetches max: 8 bytes for the header length, then the header
    /// itself (capped — headers larger than the cap are recorded as a
    /// limitation by the caller).
    ///
    /// Boundary guard: a server that ignores Range answers 200 with the
    /// WHOLE weight file. `RangeFetchDelegate` cancels in
    /// didReceive-response — before any body bytes land — so a range
    /// request can never become a weight download. Statuses other than
    /// 206 are treated as "header unavailable", not as data.
    static func safetensorsHeaderNames(id: String, revision: String,
                                       path: String, maxHeaderBytes: Int = 24 * 1024 * 1024) throws -> [String]? {
        guard let header = try safetensorsHeader(id: id, revision: revision, path: path)
        else { return nil }
        return header.keys.filter { $0 != "__metadata__" }.sorted()
    }

    /// Full safetensors header dict `{name: {dtype, shape, data_offsets}}`
    /// via Range GET — kept around because dtype+shape give exact weight
    /// bytes and param counts, independent of Hub-side stats.
    static func safetensorsHeader(id: String, revision: String,
                                  path: String, maxHeaderBytes: Int = 24 * 1024 * 1024) throws -> [String: [String: Any]]? {
        guard let first = try rangeGet(id: id, revision: revision, path: path,
                                       range: "bytes=0-7", maxBody: 8),
              first.count >= 8 else { return nil }
        // Byte-assembled LE u64 — avoid unaligned `load(as:)` traps.
        let headerLen = first.prefix(8).reduce(UInt64(0)) { ($0 << 8) | UInt64($1) }.byteSwapped
        guard headerLen > 0, headerLen <= UInt64(maxHeaderBytes) else { return nil }

        guard let headerData = try rangeGet(id: id, revision: revision, path: path,
                                            range: "bytes=8-\(8 + headerLen - 1)",
                                            maxBody: Int(headerLen)),
              headerData.count >= Int(headerLen) else { return nil }
        guard let obj = try? JSONSerialization.jsonObject(with: headerData.prefix(Int(headerLen)))
                as? [String: [String: Any]] else { return nil }
        return obj
    }

    /// Range GET helper shared by the safetensors and GGUF header reads.
    /// Returns nil (not throw) when the server doesn't honor Range —
    /// a 200 would be the whole weight file, which the delegate refuses
    /// before body bytes arrive. Throws on real network errors.
    static func rangeGet(id: String, revision: String, path: String,
                         range: String, maxBody: Int) throws -> Data? {
        guard let url = resolveURL(id: id, revision: revision, path: path) else { return nil }
        var req = authorizedRequest(url: url)
        req.setValue(range, forHTTPHeaderField: "Range")
        let result = fetch(req, maxBytes: maxBody, acceptedStatuses: [206])
        if result.refusedStatus || result.statusCode != 206 { return nil }
        if let error = result.error { throw HubError.network("\(error)") }
        return result.data
    }

    private static func resolveURL(id: String, revision: String, path: String) -> URL? {
        let encodedPath = path.split(separator: "/", omittingEmptySubsequences: false)
            .map { String($0).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? String($0) }
            .joined(separator: "/")
        let encodedRevision = revision.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)
            ?? revision
        return URL(string: "https://huggingface.co/\(id)/resolve/\(encodedRevision)/\(encodedPath)")
    }

    private static func authorizedRequest(url: URL) -> URLRequest {
        var request = URLRequest(url: url)
        if let token = ProcessInfo.processInfo.environment["HF_TOKEN"], !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.setValue("posttrainllm/0.1", forHTTPHeaderField: "User-Agent")
        return request
    }

    /// Read the GGUF metadata block (magic + kv pairs) of a .gguf file —
    /// enough for `general.architecture`, `general.file_type` (quant),
    /// `general.name`, and `<arch>.context_length`. Bounded at 8 MB; the
    /// tokenizer tokens array inflates some metadata blocks.
    public static func ggufMeta(id: String, revision: String, path: String) throws -> GGUFHeader.Meta? {
        guard let data = try rangeGet(id: id, revision: revision, path: path,
                                      range: "bytes=0-\(8 * 1024 * 1024 - 1)",
                                      maxBody: 8 * 1024 * 1024)
        else { return nil }
        return GGUFHeader.parse(data)
    }

    private struct FetchResult {
        let data: Data
        let statusCode: Int
        let error: Error?
        let tooLarge: Bool
        let refusedStatus: Bool
    }

    private static func fetch(
        _ request: URLRequest, maxBytes: Int,
        acceptedStatuses: Set<Int>? = nil
    ) -> FetchResult {
        let delegate = CappedFetchDelegate(
            maxBody: maxBytes, acceptedStatuses: acceptedStatuses)
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        let session = URLSession(
            configuration: config, delegate: delegate, delegateQueue: nil)
        session.dataTask(with: request).resume()
        delegate.semaphore.wait()
        session.finishTasksAndInvalidate()
        return FetchResult(
            data: delegate.data, statusCode: delegate.statusCode,
            error: delegate.error, tooLarge: delegate.tooLarge,
            refusedStatus: delegate.refusedStatus)
    }

    /// Receives a response only while it remains under the cap. Range
    /// requests can additionally require 206, refusing a whole-file 200
    /// before any weight bytes arrive.
    private final class CappedFetchDelegate: NSObject, URLSessionDataDelegate, @unchecked Sendable {
        let semaphore = DispatchSemaphore(value: 0)
        let maxBody: Int
        let acceptedStatuses: Set<Int>?
        var data = Data()
        var statusCode = 0
        var error: Error?
        var tooLarge = false
        var refusedStatus = false

        init(maxBody: Int, acceptedStatuses: Set<Int>?) {
            self.maxBody = maxBody
            self.acceptedStatuses = acceptedStatuses
        }

        func urlSession(_ session: URLSession, dataTask: URLSessionDataTask,
                        didReceive response: URLResponse,
                        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
            statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            let size = response.expectedContentLength
            tooLarge = size > Int64(maxBody)
            refusedStatus = acceptedStatuses.map { !$0.contains(statusCode) } ?? false
            completionHandler(tooLarge || refusedStatus ? .cancel : .allow)
        }

        func urlSession(_ session: URLSession, dataTask: URLSessionDataTask,
                        didReceive chunk: Data) {
            guard chunk.count <= maxBody - data.count else {
                tooLarge = true
                dataTask.cancel()
                return
            }
            data.append(chunk)
        }

        func urlSession(_ session: URLSession, task: URLSessionTask,
                        didCompleteWithError error: Error?) {
            if let error, !tooLarge, !refusedStatus { self.error = error }
            semaphore.signal()
        }
    }

    // MARK: - decode

    static func decodeInfo(data: Data, fallbackId: String) throws -> Info {
        let obj: [String: Any]
        do {
            obj = (try JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        } catch { throw HubError.malformed("\(error)") }
        guard !obj.isEmpty else { throw HubError.malformed("empty object") }

        var info = Info(id: (obj["id"] as? String) ?? fallbackId)
        info.sha = obj["sha"] as? String
        info.lastModified = obj["lastModified"] as? String
        info.tags = (obj["tags"] as? [String]) ?? []
        info.pipelineTag = obj["pipeline_tag"] as? String
        info.libraryName = obj["library_name"] as? String
        info.isPrivate = (obj["private"] as? Bool) ?? false

        decodeGating(obj, into: &info)
        if let disabled = obj["disabled"] as? Bool, disabled {
            info.tags.append("disabled")
        }
        decodeSiblings(obj, into: &info)
        decodeSafetensorsStats(obj, into: &info)
        info.apiConfig = obj["config"] as? [String: Any]
        decodeTransformersInfo(obj, into: &info)
        if let card = obj["cardData"] as? [String: Any] {
            info.baseModel = card["base_model"] as? String
                ?? (card["base_model"] as? [String])?.first
        }
        return info
    }

    private static func decodeGating(_ object: [String: Any], into info: inout Info) {
        if let gated = object["gated"] as? Bool { info.gated = gated }
        if let gated = object["gated"] as? String, gated != "false" {
            info.gated = true
            info.gatedKind = gated
        }
    }

    private static func decodeSiblings(_ object: [String: Any], into info: inout Info) {
        for sibling in object["siblings"] as? [[String: Any]] ?? [] {
            guard let name = sibling["rfilename"] as? String else { continue }
            info.siblings.append(Sibling(
                name: name,
                size: (sibling["size"] as? NSNumber).flatMap {
                    $0.int64Value >= 0 ? $0.int64Value : nil
                }
            ))
        }
    }

    private static func decodeSafetensorsStats(_ object: [String: Any], into info: inout Info) {
        guard let safetensors = object["safetensors"] as? [String: Any],
              let parameters = safetensors["parameters"] as? [String: Any] else { return }
        for (dtype, count) in parameters {
            if let value = (count as? NSNumber)?.int64Value, value >= 0 {
                info.safetensorsParams[dtype] = value
            }
        }
    }

    private static func decodeTransformersInfo(_ object: [String: Any], into info: inout Info) {
        guard let transformers = object["transformersInfo"] as? [String: Any] else { return }
        info.autoModel = transformers["auto_model"] as? String
        info.customClass = transformers["custom_class"] as? String
    }
}
