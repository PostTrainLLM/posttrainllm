import Foundation

/// Minimal GGUF metadata-KV parser — pure Foundation, header only.
///
/// GGUF layout (little-endian):
///   u32 magic 'GGUF' · u32 version · u64 tensor_count · u64 kv_count
///   metadata_kv[kv_count] · tensor_info[tensor_count] · align · data
///
/// metadata_kv = u64 keylen · key bytes · u32 value_type · typed value.
/// We walk only the metadata section — enough to recover
/// `general.architecture`, `general.file_type` (quant), `general.name`,
/// and `<arch>.context_length` from a ~64 KB Range fetch. Tensor info
/// and weight data are never touched.
///
/// `TinyGPTModel/GGUFReader` is the full parser + dequant; this is a
/// deliberately tiny duplicate because GGUFReader imports MLX and
/// TinyGPTCheck stays Foundation-only.
public enum GGUFHeader {

    /// (Not Sendable: `kv` holds untyped decoded values.)
    public struct Meta {
        public var version: UInt32
        public var tensorCount: UInt64
        public var kv: [String: Any]
        public var architecture: String? { kv["general.architecture"] as? String }
        public var name: String? { kv["general.name"] as? String }
        public var fileType: UInt32? {
            (kv["general.file_type"] as? UInt32) ?? (kv["general.file_type"] as? Int).map(UInt32.init)
        }
        public var contextLength: UInt64? {
            if let a = architecture,
               let v = kv["\(a).context_length"] as? UInt64 { return v }
            if let a = architecture,
               let v = kv["\(a).context_length"] as? UInt32 { return UInt64(v) }
            return nil
        }
    }

    /// llama.cpp `llama_model_ftype` enum → human quant name.
    /// Values per llama.cpp/gguf metadata; unknown codes keep a numeric
    /// label rather than guessing.
    public static func fileTypeName(_ t: UInt32) -> String {
        let table: [UInt32: String] = [
            0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
            6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1",
            10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
            14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M",
            18: "Q6_K", 19: "IQ2_XXS", 20: "IQ1_S", 21: "IQ4_NL",
            22: "IQ3_S", 23: "IQ2_XS", 24: "IQ3_XXS", 25: "IQ1_M",
            26: "IQ4_XS", 27: "BF16",
            36: "TQ1_0", 37: "TQ2_0",
            40: "MXFP4",
        ]
        return table[t] ?? "ftype \(t)"
    }

    /// GGUF dequant types TinyGPTModel/GGUFReader supports — F32, F16,
    /// Q4_0, Q8_0. K-quants and IQ formats are NOT wired for our loader
    /// (mechanical follow-up), which matters for verdict honesty: most
    /// published GGUFs are K-quants and our `gguf-load` can't dequant
    /// them even when the architecture is otherwise compatible.
    public static let loaderSupportedFileTypes: Set<UInt32> = [0, 1, 2, 8, 27]

    /// GGUF `general.architecture` values our HF-native loader maps onto
    /// the verified Llama-family set. llama.cpp arch names ≠ HF arch
    /// names ("llama" ↔ LlamaForCausalLM, "qwen3" ↔ Qwen3ForCausalLM…).
    public static let llamaFamilyArchNames: Set<String> = [
        "llama", "mistral", "qwen2", "qwen3", "phi3", "gemma", "gemma2",
        "gemma3", "smollm3", "lfm2",
    ]

    /// Parse metadata from the file's leading bytes. Returns nil if the
    /// bytes aren't GGUF or the buffer ends before the metadata section
    /// does — callers treat nil as "header unreadable", never as a
    /// verdict.
    public static func parse(_ data: Data) -> Meta? {
        data.withUnsafeBytes { raw -> Meta? in
            guard let base = raw.baseAddress else { return nil }
            var c = Cursor(base: base.assumingMemoryBound(to: UInt8.self),
                           count: raw.count)
            do {
                let magic = try c.u32()
                guard magic == 0x46554747 else { return nil }   // 'GGUF'
                let version = try c.u32()
                guard version == 2 || version == 3 else { return nil }
                let tensorCount = try c.u64()
                let kvCount = try c.u64()
                var kv: [String: Any] = [:]
                for _ in 0..<kvCount {
                    let key = try c.string()
                    let vtype = try c.u32()
                    kv[key] = try c.value(of: vtype)
                }
                return Meta(version: version, tensorCount: tensorCount, kv: kv)
            } catch {
                return nil
            }
        }
    }

    private struct Cursor {
        let base: UnsafePointer<UInt8>
        let count: Int
        var pos = 0
        struct Truncated: Error {}

        mutating func take(_ n: Int) throws -> UnsafePointer<UInt8> {
            guard pos + n <= count else { throw Truncated() }
            defer { pos += n }
            return base + pos
        }
        mutating func u8() throws -> UInt8 { try take(1).pointee }
        mutating func u16() throws -> UInt16 {
            let p = try take(2)
            return UInt16(p[0]) | UInt16(p[1]) << 8
        }
        // Byte-assembled LE reads — metadata values sit at arbitrary
        // (unaligned) offsets, so withMemoryRebound is unsafe here.
        mutating func u32() throws -> UInt32 {
            let p = try take(4)
            return UInt32(p[0]) | UInt32(p[1]) << 8 | UInt32(p[2]) << 16 | UInt32(p[3]) << 24
        }
        mutating func u64() throws -> UInt64 {
            let p = try take(8)
            var v: UInt64 = 0
            for i in 0..<8 { v |= UInt64(p[i]) << UInt64(8 * i) }
            return v
        }
        mutating func string() throws -> String {
            let n = try Int(u64())
            let p = try take(n)
            return String(decoding: UnsafeBufferPointer(start: p, count: n), as: UTF8.self)
        }
        mutating func array(of elementType: UInt32) throws -> [Any] {
            let count = try Int(u64())
            var values: [Any] = []
            values.reserveCapacity(min(count, 1024))
            for index in 0..<count {
                let element = try value(of: elementType)
                if index < 1024 { values.append(element) }
            }
            return values
        }
        mutating func value(of t: UInt32) throws -> Any {
            switch t {
            case 0: return try u8()
            case 1: return Int8(bitPattern: try u8())
            case 2: return try u16()
            case 3: return Int16(bitPattern: try u16())
            case 4: return try u32()
            case 5: return Int32(bitPattern: try u32())
            case 6:
                return Float(bitPattern: try u32())
            case 7: return try u8() != 0
            case 8: return try string()
            case 9:
                return try array(of: u32())
            case 10: return try u64()
            case 11: return Int64(bitPattern: try u64())
            case 12:
                return Double(bitPattern: try u64())
            default: throw Truncated()
            }
        }
    }
}
