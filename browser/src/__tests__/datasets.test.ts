import { describe, it, expect, vi } from "vitest";
import {
  HF_CATALOG,
  HfFetchError,
  fetchHfText,
  type HfDataset,
} from "../datasets";

describe("datasets", () => {
  describe("HF_CATALOG", () => {
    it("is a non-empty array", () => {
      expect(HF_CATALOG.length).toBeGreaterThan(0);
    });

    it("every entry has required fields", () => {
      for (const ds of HF_CATALOG) {
        expect(ds.id).toBeTruthy();
        expect(ds.label).toBeTruthy();
        expect(ds.dataset).toBeTruthy();
        expect(ds.config).toBeTruthy();
        expect(ds.split).toBeTruthy();
        expect(ds.textColumn).toBeTruthy();
        expect(ds.license).toBeTruthy();
        expect(ds.blurb).toBeTruthy();
      }
    });

    it("has unique ids", () => {
      const ids = HF_CATALOG.map((d) => d.id);
      expect(new Set(ids).size).toBe(ids.length);
    });

    it("includes tinystories", () => {
      const ts = HF_CATALOG.find((d) => d.id === "tinystories");
      expect(ts).toBeDefined();
      expect(ts?.dataset).toBe("roneneldan/TinyStories");
      expect(ts?.textColumn).toBe("text");
    });

    it("includes tiny-shakespeare", () => {
      const ts = HF_CATALOG.find((d) => d.id === "tiny-shakespeare");
      expect(ts).toBeDefined();
      expect(ts?.dataset).toBe("Trelis/tiny-shakespeare");
      expect(ts?.textColumn).toBe("Text");
    });
  });

  describe("HfFetchError", () => {
    it("constructs with message, kind, and status", () => {
      const err = new HfFetchError("test error", "auth", 401);
      expect(err.message).toBe("test error");
      expect(err.kind).toBe("auth");
      expect(err.status).toBe(401);
      expect(err.name).toBe("HfFetchError");
      expect(err).toBeInstanceOf(Error);
    });

    it("constructs without status", () => {
      const err = new HfFetchError("network error", "network");
      expect(err.kind).toBe("network");
      expect(err.status).toBeUndefined();
    });
  });

  describe("fetchHfText", () => {
    const mockDataset: HfDataset = {
      id: "test",
      label: "Test",
      dataset: "test/dataset",
      config: "default",
      split: "train",
      textColumn: "text",
      license: "MIT",
      blurb: "test blurb",
    };

    function mockFetchResponse(rows: { row: Record<string, unknown> }[]) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ rows }),
      } as Response;
    }

    it("fetches and concatenates text rows", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([
          { row: { text: "first paragraph" } },
          { row: { text: "second paragraph" } },
        ]),
      );
      try {
        const text = await fetchHfText(mockDataset, 100_000);
        expect(text).toContain("first paragraph");
        expect(text).toContain("second paragraph");
        expect(text).toContain("\n\n");
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("trims whitespace from rows", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([
          { row: { text: "  spaced  " } },
        ]),
      );
      try {
        const text = await fetchHfText(mockDataset, 100_000);
        expect(text).toBe("spaced");
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("skips non-string and empty rows", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([
          { row: { text: "valid" } },
          { row: { text: "   " } },
          { row: { text: 123 } },
          { row: { other: "wrong column" } },
        ]),
      );
      try {
        const text = await fetchHfText(mockDataset, 100_000);
        expect(text).toBe("valid");
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("stops when maxChars is reached", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([
          { row: { text: "a".repeat(50) } },
          { row: { text: "b".repeat(50) } },
        ]),
      );
      try {
        // maxChars=60 → first row (50 chars) fits, second would push to 100
        const text = await fetchHfText(mockDataset, 60);
        // The function concatenates and then slices at the end
        expect(text.length).toBeLessThanOrEqual(60);
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("throws HfFetchError on 401", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({}),
      } as Response);
      try {
        await expect(fetchHfText(mockDataset)).rejects.toThrow(HfFetchError);
        await expect(fetchHfText(mockDataset)).rejects.toMatchObject({
          kind: "auth",
          status: 401,
        });
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("throws HfFetchError on 404", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response);
      try {
        await expect(fetchHfText(mockDataset)).rejects.toMatchObject({
          kind: "not-found",
          status: 404,
        });
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("throws HfFetchError on 429 (rate limit)", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({}),
      } as Response);
      try {
        await expect(fetchHfText(mockDataset)).rejects.toMatchObject({
          kind: "ratelimit",
          status: 429,
        });
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("throws network error on fetch failure", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockRejectedValue(new Error("network down"));
      try {
        await expect(fetchHfText(mockDataset)).rejects.toMatchObject({
          kind: "network",
        });
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("throws empty error when no text returned", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([{ row: { text: "   " } }]),
      );
      try {
        await expect(fetchHfText(mockDataset)).rejects.toMatchObject({
          kind: "empty",
        });
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("calls onProgress with character count", async () => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = vi.fn().mockResolvedValue(
        mockFetchResponse([
          { row: { text: "hello" } },
          { row: { text: "world" } },
        ]),
      );
      const progressCalls: number[] = [];
      try {
        await fetchHfText(mockDataset, 100_000, (chars) => progressCalls.push(chars));
        expect(progressCalls.length).toBeGreaterThan(0);
        expect(progressCalls[progressCalls.length - 1]).toBeGreaterThan(0);
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it("sends Authorization header when token provided", async () => {
      const originalFetch = globalThis.fetch;
      let capturedHeaders: Record<string, string> = {};
      globalThis.fetch = vi.fn().mockImplementation((_url: string, opts?: { headers?: Record<string, string> }) => {
        capturedHeaders = opts?.headers ?? {};
        return Promise.resolve(mockFetchResponse([{ row: { text: "data" } }]));
      });
      try {
        await fetchHfText(mockDataset, 100_000, undefined, "hf_test_token");
        expect(capturedHeaders.Authorization).toBe("Bearer hf_test_token");
      } finally {
        globalThis.fetch = originalFetch;
      }
    });
  });
});
