/** Local-only, identity-bound portable Qwen inference; no native calibration. */
import * as ort from "onnxruntime-web/wasm";
import wasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";
import { Tokenizer } from "@huggingface/tokenizers";
import { object, type Json } from "./forecast-input";
import {
  canonical,
  decisionFiles,
  decisionItem,
  decisionManifest,
  decisionPrompt,
  selectedPrediction,
  tokenIds,
  type DecisionManifest,
} from "./decision-input";

ort.env.wasm.wasmPaths = { wasm: wasmUrl };
ort.env.wasm.numThreads = 2;
let session: ort.InferenceSession | undefined,
  tokenizer: Tokenizer | undefined,
  metadata: DecisionManifest | undefined,
  busy = false;
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<Json>) => void) | null;
  postMessage: (data: unknown) => void;
};
async function hash(bytes: ArrayBuffer) {
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (v) => v.toString(16).padStart(2, "0"),
  ).join("");
}
function encode(meta: DecisionManifest, engine: Tokenizer, value: unknown) {
  const item = decisionItem(value),
    labels = Object.keys(object(item.options));
  const encoded = labels.map(
    (label) => engine.encode(label, { add_special_tokens: false }).ids,
  );
  if (
    encoded.some((ids) => ids.length !== 1) ||
    new Set(encoded.map((ids) => ids[0])).size !== labels.length
  )
    throw Error(
      "Every option label must encode as one distinct token; use A, B, C…",
    );
  const ids = tokenIds(encoded.flat(), 26);
  const tokens = tokenIds(
    engine.encode(decisionPrompt(meta, item), { add_special_tokens: false })
      .ids,
    meta.max_tokens,
  );
  return { item, labels, ids, tokens };
}
async function logits(
  engine: ort.InferenceSession,
  tokens: number[],
  ids: number[],
) {
  const inputs = {
    tokens: new ort.Tensor("int64", BigInt64Array.from(tokens.map(BigInt)), [
      1,
      tokens.length,
    ]),
    labels: new ort.Tensor("int64", BigInt64Array.from(ids.map(BigInt)), [
      ids.length,
    ]),
  };
  try {
    const output = await engine.run(inputs);
    try {
      const value = output.logits;
      if (
        !value ||
        value.type !== "float32" ||
        value.dims.join() !== `1,${ids.length}`
      )
        throw Error("Invalid selected-logit output shape.");
      const values = Array.from(value.data as Float32Array);
      if (values.some((v) => !Number.isFinite(v)))
        throw Error("Nonfinite selected logits.");
      return values;
    } finally {
      for (const value of Object.values(output)) value.dispose();
    }
  } finally {
    for (const value of Object.values(inputs)) value.dispose();
  }
}
async function load(data: Json) {
  await session?.release();
  session = undefined;
  tokenizer = undefined;
  metadata = undefined;
  if (typeof data.manifest !== "string" || data.manifest.length > 8 * 1024 ** 2)
    throw Error("Manifest exceeds 8 MiB.");
  const meta = decisionManifest(JSON.parse(data.manifest)),
    files = object(data.files);
  for (const name of decisionFiles) {
    const bytes = files[name];
    if (
      !(bytes instanceof ArrayBuffer) ||
      bytes.byteLength !== meta.files[name].bytes ||
      (await hash(bytes)) !== meta.files[name].sha256
    )
      throw Error(`Local artifact checksum or size mismatch: ${name}`);
  }
  const identity = await hash(
    new TextEncoder().encode(
      canonical({
        format: meta.format,
        source: meta.source_identity,
        files: meta.files,
        contract_sha256: await hash(
          new TextEncoder().encode(meta.contract_json).buffer,
        ),
      }),
    ).buffer,
  );
  if (identity !== meta.model_identity)
    throw Error("Portable model identity mismatch.");
  const decoder = new TextDecoder();
  const tokens = new Tokenizer(
    JSON.parse(decoder.decode(files["tokenizer.json"] as ArrayBuffer)),
    JSON.parse(decoder.decode(files["tokenizer_config.json"] as ArrayBuffer)),
  );
  for (const vector of meta.template.vectors)
    if (
      JSON.stringify(
        tokens.encode(vector.text, { add_special_tokens: false }).ids,
      ) !== JSON.stringify(vector.ids)
    )
      throw Error("Python/browser tokenizer parity failed.");
  const engine = await ort.InferenceSession.create(
    files["model.onnx"] as ArrayBuffer,
    {
      executionProviders: ["wasm"],
      externalData: [
        {
          path: "model.onnx.data",
          data: new Uint8Array(files["model.onnx.data"] as ArrayBuffer),
        },
      ],
    },
  );
  try {
    if (
      engine.inputNames.join() !== "tokens,labels" ||
      engine.outputNames.join() !== "logits"
    )
      throw Error("Unsupported decision graph inputs/outputs.");
    for (const probe of meta.probes) {
      const encoded = encode(meta, tokens, probe.item);
      if (
        JSON.stringify(encoded.tokens) !== JSON.stringify(probe.tokens) ||
        JSON.stringify(encoded.ids) !== JSON.stringify(probe.label_ids)
      )
        throw Error("Python/browser decision prompt parity failed.");
      const values = await logits(engine, encoded.tokens, encoded.ids);
      if (
        values.some(
          (v, i) =>
            Math.abs(v - probe.logits[i]) >
            0.002 + 0.0002 * Math.abs(probe.logits[i]),
        )
      )
        throw Error("Python/browser selected-logit parity failed.");
    }
    session = engine;
    tokenizer = tokens;
    metadata = meta;
    return {
      example: { item: meta.probes[0].item, threshold: 0 },
      max_tokens: meta.max_tokens,
      model_identity: meta.model_identity,
    };
  } catch (error) {
    await engine.release();
    throw error;
  }
}
async function predict(payload: unknown) {
  if (!session || !tokenizer || !metadata)
    throw Error("Load and verify a portable Qwen package first.");
  const value = object(payload);
  if (value.calibration != null)
    throw Error(
      "Portable float32 decisions are uncalibrated; native calibration cannot be reused.",
    );
  const encoded = encode(metadata, tokenizer, value.item);
  const values = await logits(session, encoded.tokens, encoded.ids);
  return {
    predictions: [
      selectedPrediction(encoded.labels, values, value.threshold ?? 0),
    ],
    labels: encoded.labels,
    logits: values,
    prompt_tokens: encoded.tokens.length,
    model_identity: metadata.model_identity,
    source_identity: metadata.source_identity,
    runtime: "wasm",
    arithmetic: "portable float32",
    quality: "unqualified",
    native_calibration: "incompatible arithmetic identity",
    input_sha256: await hash(
      new TextEncoder().encode(JSON.stringify(encoded.item)).buffer,
    ),
    input_encoding: "browser-json-v1",
  };
}
scope.onmessage = async ({ data }) => {
  if (busy) {
    scope.postMessage({
      id: data.id,
      error: "A decision operation is already running.",
    });
    return;
  }
  busy = true;
  try {
    const result =
      data.action === "load"
        ? await load(data)
        : data.action === "predict"
          ? await predict(data.payload)
          : (() => {
              throw Error("Unsupported decision worker action.");
            })();
    scope.postMessage({ id: data.id, result });
  } catch (error) {
    scope.postMessage({
      id: data.id,
      error:
        error instanceof Error ? error.message : "Portable decision failed.",
    });
  } finally {
    busy = false;
  }
};
