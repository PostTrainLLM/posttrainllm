import { describe, expect, it } from "vitest";
import {
  manifest,
  prepare,
  quantiles,
  verify,
} from "../specialists/forecast-input";
function artifact() {
  return manifest({
    format: "posttrainllm-timestral-onnx-v1",
    model_sha256: "a".repeat(64),
    model_identity: "b".repeat(64),
    quantile_levels: [0.1, 0.5, 0.9],
    max_context: 32768,
    source: {
      timestral_revision: "a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff",
      exporter_sha256: "a".repeat(64),
      reference_sha256: "b".repeat(64),
    },
    shape: {
      targets: 1,
      context: 4,
      horizon: 2,
      past_covariates: 0,
      known_covariates: 0,
      categorical_past_covariates: 1,
      categorical_known_covariates: 1,
    },
    input_names: ["context", "observed", "past", "known"],
    probes: [{}, {}, {}],
  });
}
function row() {
  return {
    context: [[null, 2, null, 6]],
    categorical_past_covariates: [[null, 100000001, 100000002, 100000001]],
    categorical_known_covariates: [
      [null, 100000001, 100000002, 100000001, 100000001, 999],
    ],
  };
}
describe("browser Timestral input contract", () => {
  it("fits categorical means on observed, forward-filled history with distinct float64 codes", () => {
    const feeds = prepare(artifact(), row(), 2);
    expect(Array.from(feeds.context.data)).toEqual([0, 2, 0, 6]);
    expect(Array.from(feeds.observed.data)).toEqual([0, 1, 0, 1]);
    expect(Array.from(feeds.past.data)).toEqual([
      NaN,
      Math.fround(34 / 9),
      Math.fround(8 / 3),
      Math.fround(34 / 9),
    ]);
    expect(Array.from(feeds.known.data)).toEqual([
      NaN,
      Math.fround(34 / 9),
      Math.fround(8 / 3),
      Math.fround(34 / 9),
      Math.fround(34 / 9),
      Math.fround(10 / 3),
    ]);
    expect(feeds.known.dims).toEqual([1, 1, 6]);
  });
  it("never consumes future target labels", () => {
    expect(
      prepare(artifact(), { ...row(), target: [[1e20, -1e20]] }, 2),
    ).toEqual(prepare(artifact(), row(), 2));
  });
  it("retains raw categorical codes for multivariate targets", () => {
    const meta = artifact();
    meta.shape.targets = 2;
    const feeds = prepare(
      meta,
      {
        ...row(),
        context: [
          [null, 2, null, 6],
          [1, 2, 3, 4],
        ],
      },
      2,
    );
    expect(Array.from(feeds.past.data)).toEqual([
      NaN,
      Math.fround(100000001),
      Math.fround(100000002),
      Math.fround(100000001),
    ]);
  });
  it("honors explicit masks and rejects missing-only targets", () => {
    const item = { ...row(), observation_mask: [[false, false, false, true]] };
    expect(Array.from(prepare(artifact(), item, 2).past.data)).toEqual([
      NaN,
      6,
      6,
      6,
    ]);
    expect(() =>
      prepare(
        artifact(),
        { ...item, observation_mask: [[false, false, false, false]] },
        2,
      ),
    ).toThrow(/unmasked/);
    expect(() =>
      prepare(
        artifact(),
        { ...item, observation_mask: [[0, true, false, true]] },
        2,
      ),
    ).toThrow(/boolean/);
  });
  it("requires exact shape and finite input without silently ignoring extra covariates", () => {
    expect(() => prepare(artifact(), row(), 3)).toThrow(/exactly 2/);
    expect(() =>
      prepare(
        artifact(),
        { ...row(), known_covariates: [[0, 1, 0, 1, 0, 1]] },
        2,
      ),
    ).toThrow(/absent/);
    expect(() =>
      prepare(artifact(), { ...row(), context: [[1e40, 1, 2, 3]] }, 2),
    ).toThrow(/float32/);
    expect(() =>
      prepare(
        artifact(),
        { ...row(), categorical_known_covariates: [[1, 2]] },
        2,
      ),
    ).toThrow(/6 time/);
  });
  it("rejects invalid manifests and changed output/probe boundaries", () => {
    expect(() => manifest({ ...artifact(), model_sha256: "unknown" })).toThrow(
      /unidentified/,
    );
    expect(() => manifest({ ...artifact(), input_names: ["context"] })).toThrow(
      /input names/,
    );
    expect(() => manifest({ ...artifact(), probes: [] })).toThrow(
      /Three Python/,
    );
    expect(() =>
      quantiles(artifact(), [0, 1, 2, 0, 2, 1], [1, 1, 2, 3]),
    ).toThrow(/crossing/);
    expect(() => quantiles(artifact(), [0, 1, 2], [1, 1, 1, 3])).toThrow(
      /shape/,
    );
    expect(() => verify([[[0, 1, 2]]], [[[0, 1, 2.01]]])).toThrow(/parity/);
    expect(() => verify([[[0, 1, 2]]], [[[0, 1, NaN]]])).toThrow(/parity/);
    expect(() => verify([[[0, 1, 2]]], [[[0, 1, 2.00001]]])).not.toThrow();
  });
});
