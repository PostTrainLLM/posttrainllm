/** Pinned Timestral preprocessing. Float64 category identities precede float32 encoding. */
export type Json = Record<string, unknown>;
const covariates = [
  "past_covariates",
  "known_covariates",
  "categorical_past_covariates",
  "categorical_known_covariates",
] as const;
export type Manifest = {
  format: string;
  model_sha256: string;
  model_identity: string;
  quantile_levels: number[];
  max_context: number;
  shape: Record<string, number>;
  input_names: string[];
  probes: { row: Json; expected: number[][][] }[];
};
export function object(value: unknown): Json {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw Error("Expected a JSON object.");
  return value as Json;
}
function integer(value: unknown, low: number, high: number): number {
  if (!Number.isInteger(value) || Number(value) < low || Number(value) > high)
    throw Error("Invalid forecast shape.");
  return Number(value);
}
function validateSource(source: Json): void {
  if (
    source.timestral_revision !== "a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff" ||
    ![source.exporter_sha256, source.reference_sha256].every(
      (v) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v),
    )
  )
    throw Error("Forecast source provenance is missing or unsupported.");
}
function validateLevels(levels: unknown): void {
  if (
    !Array.isArray(levels) ||
    levels.length < 3 ||
    levels.length > 99 ||
    !levels.includes(0.5) ||
    levels.some(
      (v, i) =>
        typeof v !== "number" ||
        !Number.isFinite(v) ||
        v <= 0 ||
        v >= 1 ||
        (i > 0 && v <= levels[i - 1]),
    )
  )
    throw Error("Invalid forecast quantile levels.");
}
export function manifest(value: unknown): Manifest {
  const data = object(value),
    shape = object(data.shape),
    source = object(data.source);
  validateSource(source);
  if (
    data.format !== "posttrainllm-timestral-onnx-v1" ||
    typeof data.model_sha256 !== "string" ||
    !/^[a-f0-9]{64}$/.test(data.model_sha256) ||
    typeof data.model_identity !== "string" ||
    !/^[a-f0-9]{64}$/.test(data.model_identity)
  )
    throw Error("Unsupported or unidentified forecast artifact.");
  integer(shape.targets, 1, 32);
  integer(shape.context, 1, 32768);
  integer(shape.horizon, 1, 1024);
  integer(data.max_context, 1, 32768);
  for (const key of covariates) integer(shape[key], 0, 32);
  validateLevels(data.quantile_levels);
  const names = ["context", "observed"];
  if (Number(shape.past_covariates) + Number(shape.categorical_past_covariates))
    names.push("past");
  if (
    Number(shape.known_covariates) + Number(shape.categorical_known_covariates)
  )
    names.push("known");
  if (JSON.stringify(data.input_names) !== JSON.stringify(names))
    throw Error("Forecast input names do not match its shape.");
  if (!Array.isArray(data.probes) || data.probes.length !== 3)
    throw Error("Three Python forecast probes are required.");
  return data as unknown as Manifest;
}
function matrix(
  value: unknown,
  rows: number,
  length: number,
  name: string,
  categorical = false,
): number[][] {
  if (!rows) {
    if (value !== undefined)
      throw Error(`${name} is absent from this artifact's shape.`);
    return [];
  }
  if (!Array.isArray(value) || value.length !== rows)
    throw Error(`${name} must have ${rows} rows.`);
  return value.map((row) => {
    if (!Array.isArray(row) || row.length !== length)
      throw Error(`${name} must have ${length} time steps.`);
    return row.map((entry) => {
      if (entry === null) return NaN;
      if (typeof entry !== "number" || !Number.isFinite(entry))
        throw Error(`${name} requires finite numbers or null.`);
      const numeric = categorical ? entry : Math.fround(entry);
      if (!Number.isFinite(numeric))
        throw Error(`${name} exceeds float32 range.`);
      return numeric;
    });
  });
}
function encode(
  codes: number[],
  target: number[] | null,
  context: number,
): number[] {
  if (!target) return codes.map(Math.fround);
  let sum = 0,
    count = 0;
  const groups = new Map<number, { sum: number; count: number }>();
  for (let i = 0; i < context; i++) {
    const key = codes[i],
      group = groups.get(key) ?? { sum: 0, count: 0 };
    if (Number.isFinite(target[i])) {
      sum += target[i];
      count++;
      group.sum += target[i];
      group.count++;
    }
    groups.set(key, group);
  }
  const mean = count ? sum / count : 0;
  return codes.map((key, i) => {
    if (i < context && !Number.isFinite(target[i]) && Number.isNaN(key))
      return NaN;
    const group = groups.get(key);
    return Math.fround(group ? (mean + group.sum) / (1 + group.count) : mean);
  });
}
export type Feed = {
  type: "float32" | "bool";
  data: Float32Array | Uint8Array;
  dims: number[];
};
export function prepare(
  meta: Manifest,
  input: unknown,
  horizon: unknown,
): Record<string, Feed> {
  const row = object(input),
    shape = meta.shape;
  if (horizon !== shape.horizon)
    throw Error(`This artifact forecasts exactly ${shape.horizon} steps.`);
  const context = matrix(row.context, shape.targets, shape.context, "context");
  const mask = context.map((series) => series.map(Number.isFinite));
  if (row.observation_mask !== undefined) {
    const provided = row.observation_mask;
    if (!Array.isArray(provided) || provided.length !== shape.targets)
      throw Error("Observation mask shape mismatch.");
    provided.forEach((series, r) => {
      if (
        !Array.isArray(series) ||
        series.length !== shape.context ||
        series.some((v) => typeof v !== "boolean")
      )
        throw Error("Observation mask must be boolean and match context.");
      series.forEach((v, i) => {
        mask[r][i] = mask[r][i] && v;
      });
    });
  }
  if (mask.some((series) => !series.some(Boolean)))
    throw Error("Each target needs an unmasked observation.");
  let target: number[] | null = null;
  if (shape.targets === 1) {
    let last = 0,
      started = false;
    target = context[0].map((value, i) => {
      if (mask[0][i]) {
        last = value;
        started = true;
      }
      return started && i >= shape.context - meta.max_context ? last : NaN;
    });
  }
  const feeds: Record<string, Feed> = {
    context: {
      type: "float32",
      data: Float32Array.from(
        context.flatMap((series, r) =>
          series.map((v, i) => (mask[r][i] ? v : 0)),
        ),
      ),
      dims: [1, shape.targets, shape.context],
    },
    observed: {
      type: "bool",
      data: Uint8Array.from(mask.flat().map(Number)),
      dims: [1, shape.targets, shape.context],
    },
  };
  for (const [name, key] of [
    ["past_covariates", "past"],
    ["known_covariates", "known"],
  ]) {
    const categorical = "categorical_" + name;
    const length = shape.context + (key === "known" ? shape.horizon : 0);
    const numeric = matrix(row[name], shape[name], length, name);
    const codes = matrix(
      row[categorical],
      shape[categorical],
      length,
      categorical,
      true,
    );
    const rows = [
      ...numeric,
      ...codes.map((series) => encode(series, target, shape.context)),
    ];
    if (rows.length)
      feeds[key] = {
        type: "float32",
        data: Float32Array.from(rows.flat()),
        dims: [1, rows.length, length],
      };
  }
  return feeds;
}
export function quantiles(
  meta: Manifest,
  values: ArrayLike<number>,
  dims: readonly number[],
): number[][][] {
  const { targets, horizon } = meta.shape,
    count = meta.quantile_levels.length;
  if (
    JSON.stringify(dims) !== JSON.stringify([1, targets, horizon, count]) ||
    values.length !== targets * horizon * count
  )
    throw Error("Forecast output shape mismatch.");
  return Array.from({ length: targets }, (_, r) =>
    Array.from({ length: horizon }, (_, t) => {
      const offset = (r * horizon + t) * count;
      const result = Array.from({ length: count }, (_, q) =>
        Number(values[offset + q]),
      );
      if (
        result.some(
          (v, q) => !Number.isFinite(v) || (q > 0 && v < result[q - 1]),
        )
      )
        throw Error("Forecast contains nonfinite or crossing quantiles.");
      return result;
    }),
  );
}
export function verify(actual: number[][][], expected: unknown): void {
  if (!Array.isArray(expected) || actual.length !== expected.length)
    throw Error("Python probe shape mismatch.");
  actual.forEach((series, r) => {
    const target = expected[r];
    if (!Array.isArray(target) || series.length !== target.length)
      throw Error("Python probe shape mismatch.");
    series.forEach((row, t) => {
      if (!Array.isArray(target[t]) || row.length !== target[t].length)
        throw Error("Python probe shape mismatch.");
      row.forEach((v, q) => {
        const reference = target[t][q];
        if (
          typeof reference !== "number" ||
          !Number.isFinite(reference) ||
          Math.abs(v - reference) > 0.002 + 0.0002 * Math.abs(reference)
        )
          throw Error("Browser forecast failed Python numerical parity.");
      });
    });
  });
}
