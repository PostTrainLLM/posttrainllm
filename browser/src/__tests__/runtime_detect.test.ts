import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  detectBrowser,
  detectHardware,
  recommendModel,
  type Hardware,
  type MachineTier,
} from "../runtime_detect";

describe("runtime_detect", () => {
  describe("detectBrowser", () => {
    it("detects Chrome", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 (Macintosh) Chrome/120.0.0.0",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("Chrome");
        expect(info.chromium).toBe(true);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });

    it("detects Edge", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 (Windows) Edg/120.0.0.0",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("Edge");
        expect(info.chromium).toBe(true);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });

    it("detects Firefox", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 (X11; Linux) Firefox/121.0",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("Firefox");
        expect(info.chromium).toBe(false);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });

    it("detects Safari", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 (Macintosh) Safari/605.1.15",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("Safari");
        expect(info.chromium).toBe(false);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });

    it("detects HeadlessChrome (Playwright)", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 HeadlessChrome/120.0.0.0",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("Chrome");
        expect(info.chromium).toBe(true);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });

    it("returns fallback for unknown browser", () => {
      const original = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "SomeUnknownBrowser/1.0",
        configurable: true,
      });
      try {
        const info = detectBrowser();
        expect(info.name).toBe("this browser");
        expect(info.chromium).toBe(false);
      } finally {
        Object.defineProperty(navigator, "userAgent", {
          value: original,
          configurable: true,
        });
      }
    });
  });

  describe("recommendModel param estimation", () => {
    it("approxParams is positive for all tiers", () => {
      for (const cpuMs of [5, 12, 25, 50]) {
        const hw: Hardware = { cores: 8, deviceMemoryGB: 16, cpuProbeMs: cpuMs };
        const rec = recommendModel(hw);
        expect(rec.approxParams).toBeGreaterThan(0);
      }
    });

    it("approxParams = 256*d + ctx*d + layers*12*d*d (verified via strong tier)", () => {
      // strong: ctx=128, layers=4, dModel=144
      // = 256*144 + 128*144 + 4*12*144*144 = 36864 + 18432 + 995328 = 1050624
      const hw: Hardware = { cores: 8, deviceMemoryGB: 16, cpuProbeMs: 5 };
      const rec = recommendModel(hw);
      if (rec.tier === "strong") {
        expect(rec.approxParams).toBe(256 * 144 + 128 * 144 + 4 * 12 * 144 * 144);
      }
    });
  });

  describe("recommendModel", () => {
    const makeHw = (cpuMs: number, cores: number, memGB: number | null): Hardware => ({
      cores,
      deviceMemoryGB: memGB,
      cpuProbeMs: cpuMs,
    });

    it("recommends 'strong' for fast CPU + many cores", () => {
      const hw = makeHw(5, 8, 16);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("strong");
      expect(rec.ctx).toBe(128);
      expect(rec.layers).toBe(4);
      expect(rec.dModel).toBe(144);
      expect(rec.approxParams).toBeGreaterThan(0);
    });

    it("recommends 'capable' for medium-fast CPU", () => {
      const hw = makeHw(12, 8, 8);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("capable");
      expect(rec.ctx).toBe(96);
    });

    it("recommends 'standard' for mid-range CPU", () => {
      const hw = makeHw(25, 4, 8);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("standard");
      expect(rec.ctx).toBe(64);
    });

    it("recommends 'modest' for slow CPU", () => {
      const hw = makeHw(50, 2, 4);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("modest");
      expect(rec.ctx).toBe(32);
    });

    it("downgrades strong to capable when cores <= 4", () => {
      const hw = makeHw(5, 4, 16);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("capable");
    });

    it("downgrades to standard when cores <= 2", () => {
      const hw = makeHw(5, 2, 16);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("standard");
    });

    it("downgrades to modest when deviceMemory <= 2GB", () => {
      const hw = makeHw(5, 8, 2);
      const rec = recommendModel(hw);
      expect(rec.tier).toBe("modest");
    });

    it("all tiers have a note string", () => {
      for (const tier of ["modest", "standard", "capable", "strong"] as MachineTier[]) {
        const cpuMs = tier === "strong" ? 5 : tier === "capable" ? 12 : tier === "standard" ? 25 : 50;
        const hw = makeHw(cpuMs, 8, 16);
        const rec = recommendModel(hw);
        if (rec.tier === tier) {
          expect(rec.note).toBeTruthy();
        }
      }
    });
  });
});
