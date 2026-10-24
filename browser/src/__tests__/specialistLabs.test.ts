import { afterEach, describe, expect, it, vi } from "vitest";
import { keyBytes, sampleInput } from "../specialists/labs";

describe("specialist raw terminal input", () => {
  const key = (
    value: string,
    ctrlKey = false,
    metaKey = false,
    altKey = false,
  ) => keyBytes({ key: value, ctrlKey, metaKey, altKey });

  it("sends terminal escape sequences and control bytes", () => {
    expect(key("ArrowLeft")).toEqual([27, 91, 68]);
    expect(key("Enter")).toEqual([13]);
    expect(key("Backspace")).toEqual([127]);
    expect(key("a", true)).toEqual([1]);
    expect(key("x", false, false, true)).toEqual([27, 120]);
  });

  it("preserves Mac shortcuts and rejects unsupported character input", () => {
    expect(key("c", false, true)).toBeNull();
    expect(key("é")).toBeNull();
    expect(key("Shift")).toBeNull();
  });
});

describe("specialist examples", () => {
  it("keeps target future out of the forecasting context", () => {
    const prediction = sampleInput("forecast", "predict") as {
      item: {
        context: number[][];
        known_covariates: number[][];
        target?: number[][];
      };
      horizon: number;
    };
    expect(prediction.item.target).toBeUndefined();
    expect(prediction.item.known_covariates[0].length).toBe(
      prediction.item.context[0].length + prediction.horizon,
    );
  });

  it("does not invent a ceiling receipt or calibration dataset", () => {
    expect(sampleInput("decision", "eval").ceiling).toEqual({});
    expect(sampleInput("decision", "calibrate").scores).toEqual([]);
    expect(sampleInput("terminal", "eval").ceiling).toEqual({});
  });
});

describe("private lab telemetry boundary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("does not initialize the SDK on a telemetry-disabled page", async () => {
    vi.stubGlobal("document", {
      documentElement: { dataset: { telemetry: "disabled" } },
    });
    vi.stubEnv("VITE_POSTHOG_KEY", "test-public-project-key");
    const { initAnalytics } = await import("../analytics");
    expect(initAnalytics()).toBe(false);
  });
});
