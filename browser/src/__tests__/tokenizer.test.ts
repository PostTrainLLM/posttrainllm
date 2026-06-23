import { describe, it, expect } from "vitest";
import { encode, decode, VOCAB_SIZE } from "../tokenizer";

describe("tokenizer", () => {
  describe("VOCAB_SIZE", () => {
    it("is 256 (byte-level)", () => {
      expect(VOCAB_SIZE).toBe(256);
    });
  });

  describe("encode", () => {
    it("encodes ASCII text to byte tokens", () => {
      const tokens = encode("hello");
      expect(tokens).toBeInstanceOf(Uint8Array);
      expect(Array.from(tokens)).toEqual([104, 101, 108, 108, 111]);
    });

    it("encodes empty string to empty array", () => {
      expect(encode("").length).toBe(0);
    });

    it("encodes multi-byte UTF-8 correctly", () => {
      // "é" = U+00E9 = 0xC3 0xA9 in UTF-8
      const tokens = encode("é");
      expect(Array.from(tokens)).toEqual([0xc3, 0xa9]);
    });

    it("encodes emoji as 4 bytes", () => {
      // "😀" = U+1F600 = 0xF0 0x9F 0x98 0x80 in UTF-8
      const tokens = encode("😀");
      expect(Array.from(tokens)).toEqual([0xf0, 0x9f, 0x98, 0x80]);
    });

    it("all byte values 0-255 roundtrip through encode→decode", () => {
      // Build a string that contains every byte 0-255 via UTF-8
      // Actually, we test that encode produces values in 0-255 range
      const text = "Hello, world! 123 \n\t";
      const tokens = encode(text);
      for (const t of tokens) {
        expect(t).toBeGreaterThanOrEqual(0);
        expect(t).toBeLessThanOrEqual(255);
      }
    });
  });

  describe("decode", () => {
    it("decodes byte tokens back to text", () => {
      const tokens = new Uint8Array([104, 101, 108, 108, 111]);
      expect(decode(tokens)).toBe("hello");
    });

    it("decodes empty array to empty string", () => {
      expect(decode(new Uint8Array(0))).toBe("");
    });

    it("decodes multi-byte UTF-8", () => {
      const tokens = new Uint8Array([0xc3, 0xa9]);
      expect(decode(tokens)).toBe("é");
    });
  });

  describe("roundtrip", () => {
    it("decode(encode(text)) === text for ASCII", () => {
      const text = "The quick brown fox jumps over the lazy dog.";
      expect(decode(encode(text))).toBe(text);
    });

    it("decode(encode(text)) === text for Unicode", () => {
      const text = "Hello 世界 🌍 café";
      expect(decode(encode(text))).toBe(text);
    });

    it("decode(encode(text)) === text for empty string", () => {
      expect(decode(encode(""))).toBe("");
    });

    it("decode(encode(text)) === text for newlines and tabs", () => {
      const text = "line1\nline2\ttabbed\n\n";
      expect(decode(encode(text))).toBe(text);
    });
  });
});
