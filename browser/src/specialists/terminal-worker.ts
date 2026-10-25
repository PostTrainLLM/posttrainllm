/** Isolated terminal inference; imports local files, never calls the Python API. */
import { TinyGptBackend } from "../backend";
import { GpuModel } from "../../../webgpu/gpu_model";
import { createGpuContext } from "../../../webgpu/tensor";
import { validateConfig } from "./terminal-shapes";
import {
  allowed,
  applyDelta,
  eventTokens,
  screen,
  snapshot,
  type Screen,
} from "./terminal-codec";

type Json = Record<string, unknown>;
let predict: ((ids: number[]) => Promise<Float32Array>) | undefined;
let release: (() => void) | undefined;
let current: Screen | undefined;
let history: number[] = [],
  resets = 0,
  contextLength = 0;
const scope = self as unknown as {
  onmessage: ((event: MessageEvent) => void) | null;
  postMessage: (data: unknown) => void;
};

function half(bits: number): number {
  const sign = bits & 0x8000 ? -1 : 1,
    exponent = (bits >> 10) & 31,
    mantissa = bits & 1023;
  return exponent === 31
    ? sign * (mantissa ? NaN : Infinity)
    : sign *
        (exponent
          ? 2 ** (exponent - 15) * (1 + mantissa / 1024)
          : (2 ** -14 * mantissa) / 1024);
}

function best(values: ArrayLike<number>): number {
  let index = 0;
  for (let i = 1; i < values.length; i++)
    if (values[i] > values[index]) index = i;
  return index;
}

async function load(text: string, provider: string): Promise<Json> {
  release?.();
  release = undefined;
  predict = undefined;
  current = undefined;
  const bundle = JSON.parse(text);
  const c = bundle.config;
  if (
    bundle.schema !== "posttrainllm-terminal-browser-v1" ||
    bundle.codec !== "posttrainllm-terminal-v1" ||
    !["f32", "f16"].includes(bundle.dtype)
  )
    throw new Error("Unsupported terminal inference artifact.");
  const expectedSizes = validateConfig(c),
    count = expectedSizes.reduce((a, b) => a + b, 0);
  if (
    count > 5_000_000 ||
    JSON.stringify(bundle.parameter_sizes) !== JSON.stringify(expectedSizes)
  )
    throw new Error("Terminal artifact shape exceeds the portable envelope.");
  const bytes = Uint8Array.from(atob(bundle.weights_base64), (c) =>
    c.charCodeAt(0),
  );
  if (bytes.length !== count * (bundle.dtype === "f32" ? 4 : 2))
    throw new Error("Terminal weight length mismatch.");
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
  if (hash !== bundle.weights_sha256)
    throw new Error("Terminal weight checksum mismatch.");
  const view = new DataView(bytes.buffer),
    weights = new Float32Array(count);
  for (let i = 0; i < count; i++)
    weights[i] =
      bundle.dtype === "f32"
        ? view.getFloat32(i * 4, true)
        : half(view.getUint16(i * 2, true));
  if (weights.some((v) => !Number.isFinite(v)))
    throw new Error("Nonfinite terminal weights.");
  const config = {
    vocab: 333,
    ctx: c.context_length,
    layers: c.n_layers,
    heads: c.n_heads,
    dModel: c.d_model,
    dMlp: c.d_mlp,
    seed: 7,
  };
  if (provider === "wasm") {
    const model = (await TinyGptBackend.load()).createModel(config);
    release = () => model.free();
    model.importWeights(weights);
    predict = async (ids) => model.forwardLogits(ids);
  } else if (provider === "webgpu") {
    const context = await createGpuContext();
    if (!context)
      throw new Error("WebGPU is unavailable. Select WASM instead.");
    const model = new GpuModel(context, config);
    release = () => {
      model.destroy();
      context.device.destroy();
    };
    const state = new ArrayBuffer(4 + count * 12),
      stateFloats = new Float32Array(state);
    let src = 0,
      dst = 1;
    for (const size of expectedSizes) {
      stateFloats.set(weights.subarray(src, src + size), dst);
      src += size;
      dst += size * 3;
    }
    model.importState(state);
    predict = async (ids) => (await model.forwardLogits(ids)).slice(-333);
  } else throw new Error("Choose WASM or WebGPU.");
  contextLength = c.context_length;
  const probes = bundle.parity?.probes;
  if (!Array.isArray(probes) || probes.length !== 3)
    throw new Error("Three Python parity probes are required.");
  let maximum = 0;
  for (const probe of probes) {
    if (
      !Array.isArray(probe.tokens) ||
      !probe.tokens.length ||
      probe.tokens.length > contextLength ||
      probe.tokens.some(
        (id: number) => !Number.isInteger(id) || id < 0 || id >= 333,
      ) ||
      !Array.isArray(probe.logits) ||
      probe.logits.length !== 333 ||
      probe.logits.some((n: number) => !Number.isFinite(n))
    )
      throw new Error("Invalid Python parity probe.");
    const actual = await predict(probe.tokens);
    for (let i = 0; i < 333; i++)
      maximum = Math.max(maximum, Math.abs(actual[i] - probe.logits[i]));
    if (
      actual.some((v) => !Number.isFinite(v)) ||
      best(actual) !== best(probe.logits)
    )
      throw new Error("Terminal parity failed: token ranking changed.");
  }
  if (maximum > (bundle.dtype === "f32" ? 0.002 : 0.05))
    throw new Error(`Terminal parity failed: maximum logit error ${maximum}.`);
  history = [];
  resets = 0;
  return {
    provider,
    dtype: bundle.dtype,
    maximum_logit_error: maximum,
    parity_probes: probes.length,
    weights_sha256: hash,
    quality: "unqualified; numerical parity only",
    inference_only: true,
  };
}

async function step(payload: Json): Promise<Json> {
  if (!predict) throw new Error("Load a verified terminal artifact first.");
  if (payload.parallel)
    throw new Error(
      "Browser terminal uses sequential decoding. Select Python for parallel draft verification.",
    );
  if (!payload.session || !current) {
    current = screen(payload.screen);
    history = snapshot(current);
    resets = 0;
  }
  const original = current;
  let prefix = [...history, ...eventTokens(payload.event as Json)];
  const reserve = original.lines.length * (original.lines[0].length + 6) + 6;
  if (prefix.length + reserve > contextLength) {
    prefix = [...snapshot(original), ...eventTokens(payload.event as Json)];
    resets++;
  }
  if (prefix.length + reserve > contextLength)
    throw new Error("Screen exceeds this model's context.");
  const tokens: number[] = [],
    started = performance.now();
  for (;;) {
    const candidates = allowed(tokens, original);
    if (!candidates.length) break;
    if (
      performance.now() - started > 30_000 ||
      prefix.length + tokens.length >= contextLength
    )
      throw new Error("Terminal inference budget exceeded; reset session.");
    const values = await predict([...prefix, ...tokens]);
    if (candidates.some((id) => !Number.isFinite(values[id])))
      throw new Error("Nonfinite terminal logits.");
    tokens.push(candidates[best(candidates.map((id) => values[id]))]);
  }
  current = applyDelta(original, tokens);
  history = [...prefix, ...tokens];
  return {
    result: {
      screen: current,
      tokens,
      context_resets: resets,
      session: "browser-terminal",
    },
    measurements: { elapsed_seconds: (performance.now() - started) / 1000 },
    inference_only: true,
  };
}

let queue = Promise.resolve();
scope.onmessage = (event) => {
  queue = queue.then(async () => {
    const { id, command, ...payload } = event.data;
    try {
      if (command !== "load" && command !== "predict")
        throw new Error("Unknown terminal worker command.");
      const result =
        command === "load"
          ? await load(payload.text, payload.provider)
          : await step(payload);
      scope.postMessage({ id, result });
    } catch (error) {
      if (command === "load") {
        release?.();
        release = undefined;
        predict = undefined;
      }
      current = undefined;
      history = [];
      scope.postMessage({
        id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });
};
