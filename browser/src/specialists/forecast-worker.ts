/** Browser-owned Timestral inference. Model files and inputs stay in this worker. */
import { ort } from "./browser-ort";
import {
  manifest,
  object,
  prepare,
  quantiles,
  verify,
  type Manifest,
  type Json,
} from "./forecast-input";

let session: ort.InferenceSession | undefined;
let metadata: Manifest | undefined;
let busy = false;
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<Json>) => void) | null;
  postMessage: (data: unknown) => void;
};
async function hash(value: ArrayBuffer): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", value));
  return Array.from(bytes, (v) => v.toString(16).padStart(2, "0")).join("");
}
async function predict(
  engine: ort.InferenceSession,
  meta: Manifest,
  item: unknown,
  horizon: unknown,
) {
  const feeds: Record<string, ort.Tensor> = {};
  for (const [name, input] of Object.entries(prepare(meta, item, horizon)))
    feeds[name] = new ort.Tensor(input.type, input.data, input.dims);
  try {
    const output = await engine.run(feeds);
    try {
      const value = output.quantiles;
      if (!value || value.type !== "float32")
        throw Error("Unexpected forecast output type.");
      return quantiles(meta, value.data as Float32Array, value.dims);
    } finally {
      for (const value of Object.values(output)) value.dispose();
    }
  } finally {
    for (const value of Object.values(feeds)) value.dispose();
  }
}
async function load(payload: Json): Promise<Json> {
  metadata = undefined;
  await session?.release();
  session = undefined;
  if (
    typeof payload.manifest !== "string" ||
    payload.manifest.length > 64 * 1024 ** 2 ||
    !(payload.model instanceof ArrayBuffer) ||
    payload.model.byteLength > 1024 ** 3
  )
    throw Error("Select a manifest up to 64 MiB and ONNX model up to 1 GiB.");
  const meta = manifest(JSON.parse(payload.manifest));
  if ((await hash(payload.model)) !== meta.model_sha256)
    throw Error("Model does not match its manifest checksum.");
  const candidate = await ort.InferenceSession.create(
    new Uint8Array(payload.model),
    { executionProviders: ["wasm"] },
  );
  try {
    if (
      JSON.stringify(candidate.inputNames) !== JSON.stringify(meta.input_names)
    )
      throw Error("ONNX inputs do not match the manifest.");
    for (const probe of meta.probes)
      verify(
        await predict(candidate, meta, probe.row, meta.shape.horizon),
        probe.expected,
      );
    session = candidate;
    metadata = meta;
    return {
      ready: true,
      shape: meta.shape,
      example: { item: meta.probes[0].row, horizon: meta.shape.horizon },
    };
  } catch (error) {
    await candidate.release();
    throw error;
  }
}
async function execute(payload: Json): Promise<Json> {
  if (!session || !metadata)
    throw Error("Load and verify a forecast artifact first.");
  const start = performance.now(),
    item = object(payload.item);
  const values = await predict(session, metadata, item, payload.horizon);
  const median = metadata.quantile_levels.indexOf(0.5);
  return {
    result: {
      id: item.id,
      quantiles: values,
      quantile_levels: metadata.quantile_levels,
      median: values.map((row) => row.map((step) => step[median])),
      model_identity: metadata.model_identity,
      model_sha256: metadata.model_sha256,
      quality: "unqualified",
      runtime: "wasm",
      input_sha256: await hash(
        new TextEncoder().encode(JSON.stringify(item)).buffer as ArrayBuffer,
      ),
      input_encoding: "browser-json-v1",
    },
    measurements: {
      elapsed_seconds: (performance.now() - start) / 1000,
      process_peak_rss_bytes: null,
      paid_usd: 0,
    },
  };
}
scope.onmessage = async (event: MessageEvent<Json>) => {
  const id = event.data.id;
  if (busy) {
    scope.postMessage({
      id,
      error: "A browser forecast operation is already running.",
    });
    return;
  }
  busy = true;
  try {
    const result =
      event.data.action === "load"
        ? await load(event.data)
        : await execute(object(event.data.payload));
    scope.postMessage({ id, result });
  } catch (error) {
    scope.postMessage({
      id,
      error:
        error instanceof Error ? error.message : "Browser forecast failed.",
    });
  } finally {
    busy = false;
  }
};
