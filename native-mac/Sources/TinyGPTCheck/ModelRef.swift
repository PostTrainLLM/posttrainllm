import Foundation

/// Parses a user-supplied Hugging Face model reference into a canonical
/// (id, revision, filePath) triple. Accepted shapes:
///
///   https://huggingface.co/owner/repo
///   https://huggingface.co/owner/repo/tree/<rev>
///   https://huggingface.co/owner/repo/blob/<rev>/<path>
///   https://huggingface.co/owner/repo/resolve/<rev>/<path>
///   https://hf.co/owner/repo[/...]          (same shapes, short domain)
///   owner/repo                              (bare id → revision "main")
///
/// Dataset and Space URLs are rejected up front — they are a different
/// repo kind on the Hub and the checker only speaks `api/models`.
public struct ModelRef: Equatable, Sendable {
    public let id: String             // "owner/repo"
    public let revision: String       // default "main"
    public let filePath: String?      // set for /blob/ and /resolve/ URLs

    public enum ParseError: Error, CustomStringConvertible, Equatable {
        case empty
        case notHuggingFaceURL(String)
        case notAModelRepo(kind: String, id: String)  // datasets / spaces
        case missingRepo(String)
        case invalidRepo(String)

        public var description: String {
            switch self {
            case .empty:
                return "empty input — paste a Hugging Face model URL or owner/repo"
            case .notHuggingFaceURL(let s):
                return "'\(s)' is not a huggingface.co URL and not an owner/repo id"
            case .notAModelRepo(let kind, let id):
                return "'\(id)' is a Hugging Face \(kind), not a model repository — model-check only inspects models"
            case .missingRepo(let s):
                return "'\(s)' doesn't name a model — expected owner/repo"
            case .invalidRepo(let s):
                return "'\(s)' is not a valid Hugging Face owner/repo id"
            }
        }
    }

    public static func parse(_ raw: String) throws -> ModelRef {
        let input = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { throw ParseError.empty }

        // Bare owner/repo fast path (no scheme, no host).
        if !input.contains("://") && !input.contains(" ") {
            let parts = input.split(separator: "/", omittingEmptySubsequences: true)
            if parts.count == 2, isValidRepoID(input) {
                return ModelRef(id: input, revision: "main", filePath: nil)
            }
            if parts.count != 2 { throw ParseError.missingRepo(input) }
            throw ParseError.invalidRepo(input)
        }

        guard let url = URL(string: input),
              let host = url.host?.lowercased(),
              host == "huggingface.co" || host == "hf.co" || host == "www.huggingface.co" else {
            throw ParseError.notHuggingFaceURL(input)
        }

        // Split the percent-encoded path first, then decode each component.
        // URL.path decodes `%2F` before splitting, which turns a revision such
        // as `refs%2Fpr%2F1` into three path components and silently targets a
        // different ref/file pair.
        let encodedComponents = url.path(percentEncoded: true)
            .split(separator: "/", omittingEmptySubsequences: true)
            .map(String.init)
        var comps = encodedComponents.map(decodedPathComponent)
        guard !comps.isEmpty else { throw ParseError.missingRepo(input) }

        // Repo-kind prefixes: /datasets/<id>, /spaces/<id> are not models.
        if comps[0] == "datasets" || comps[0] == "spaces" {
            let id = comps.dropFirst().prefix(2).joined(separator: "/")
            throw ParseError.notAModelRepo(kind: comps[0], id: id.isEmpty ? comps[0] : id)
        }
        guard comps.count >= 2 else { throw ParseError.missingRepo(input) }

        let id = "\(comps[0])/\(comps[1])"
        guard isValidRepoID(id) else { throw ParseError.invalidRepo(id) }
        comps = Array(comps.dropFirst(2))

        var revision = "main"
        var filePath: String? = nil
        if let first = comps.first {
            switch first {
            case "tree":
                if comps.count >= 2 { revision = comps[1] }
            case "blob", "resolve":
                if comps.count >= 2 {
                    revision = comps[1]
                    if comps.count > 2 {
                        filePath = comps.dropFirst(2).joined(separator: "/")
                    }
                }
            default:
                break  // /discussions, /commits, etc. — repo root still identified
            }
        }
        return ModelRef(id: id, revision: revision, filePath: filePath)
    }

    private static func decodedPathComponent(_ encoded: String) -> String {
        return encoded.removingPercentEncoding ?? encoded
    }

    private static func isValidRepoID(_ id: String) -> Bool {
        guard id.utf8.count <= 96 else { return false }
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_./"))
        guard id.unicodeScalars.allSatisfy(allowed.contains) else { return false }
        return id.split(separator: "/", omittingEmptySubsequences: false).allSatisfy { part in
            !part.isEmpty && part.first != "." && part.first != "-"
                && part.last != "." && part.last != "-" && !part.contains("..")
        }
    }
}
