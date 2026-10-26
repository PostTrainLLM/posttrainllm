/** Own the local decision worker, its files, cancellation and bounded requests. */
import { decisionFiles } from "./decision-input";
import { object, type Json } from "./forecast-input";

export function setupBrowserDecision(
  root: HTMLElement,
  changed: () => void,
  status: (text: string) => void,
  example: (value: Json) => void,
) {
  const control = <T extends HTMLElement>(name: string) =>
    root.querySelector<T>(`#sp-decision-${name}`)!;
  const provider = control<HTMLSelectElement>("provider"),
    files = control<HTMLInputElement>("files"),
    sampleButton = control<HTMLButtonElement>("example");
  let worker: Worker | undefined,
    generation = 0,
    serial = 0,
    verified = false,
    loading = false,
    sample: Json | undefined;
  let pending:
    | {
        id: number;
        resolve: (value: Json) => void;
        reject: (error: Error) => void;
        timer: ReturnType<typeof setTimeout>;
      }
    | undefined;
  function stop(notify = true) {
    generation++;
    worker?.terminate();
    worker = undefined;
    verified = false;
    loading = false;
    sample = undefined;
    sampleButton.disabled = true;
    if (pending) {
      clearTimeout(pending.timer);
      pending.reject(Error("Browser decision stopped."));
      pending = undefined;
    }
    if (notify) changed();
  }
  function request(data: Json, transfer: ArrayBuffer[] = []): Promise<Json> {
    if (!worker || pending)
      return Promise.reject(
        Error("Load a package and wait for the current operation."),
      );
    return new Promise((resolve, reject) => {
      const id = ++serial;
      const timer = setTimeout(() => {
        stop();
        status(
          "Browser decision exceeded its 45-second budget. Reload to retry or export a smaller model/prompt limit.",
        );
      }, 45_000);
      pending = { id, resolve, reject, timer };
      try {
        worker!.postMessage({ ...data, id }, transfer);
      } catch (error) {
        clearTimeout(timer);
        pending = undefined;
        reject(
          error instanceof Error
            ? error
            : Error("Could not transfer decision input."),
        );
      }
    });
  }
  function receive(event: MessageEvent<Json>, epoch: number) {
    if (epoch !== generation || !pending || event.data.id !== pending.id)
      return;
    const current = pending;
    pending = undefined;
    clearTimeout(current.timer);
    if (event.data.error) current.reject(Error(String(event.data.error)));
    else current.resolve(object(event.data.result));
  }
  async function load() {
    stop();
    const epoch = generation;
    try {
      const selected = packageFiles(provider.value, files.files);
      loading = true;
      status(
        "Reading local package, verifying tokenizer and three Python logit probes…",
      );
      const manifest = await selected
        .find((file) => file.name === "manifest.json")!
        .text();
      const buffers: Record<string, ArrayBuffer> = {};
      for (const file of selected) {
        if (epoch !== generation) return;
        if (file.name !== "manifest.json")
          buffers[file.name] = await file.arrayBuffer();
      }
      if (epoch !== generation) return;
      worker = new Worker(new URL("./decision-worker.ts", import.meta.url), {
        type: "module",
      });
      worker.onmessage = (event) => receive(event, epoch);
      worker.onerror = () => {
        if (epoch === generation) {
          stop();
          status("Browser decision worker failed and was stopped.");
        }
      };
      const result = await request(
        { action: "load", manifest, files: buffers },
        Object.values(buffers),
      );
      if (epoch !== generation) return;
      loading = false;
      verified = true;
      sample = object(result.example);
      sampleButton.disabled = false;
      changed();
      status(
        `Browser decision ready · portable float32 · up to ${result.max_tokens} tokens. Native calibration is incompatible; confidence and model quality remain unqualified.`,
      );
    } catch (error) {
      if (epoch === generation) {
        stop();
        status(
          error instanceof Error
            ? error.message
            : "Decision package load failed.",
        );
      }
    }
  }
  control("load").addEventListener("click", () => void load());
  control("stop").addEventListener("click", () => {
    stop();
    status("Browser decision stopped.");
  });
  sampleButton.addEventListener("click", () => {
    if (sample) example(sample);
  });
  provider.addEventListener("change", () => {
    stop();
    status(
      provider.value === "wasm"
        ? "Select the five local package files to use browser decisions."
        : "Python decisions selected. Connect your local runtime.",
    );
  });
  files.addEventListener("change", () => {
    stop();
    status("Package files changed. Load and verify before prediction.");
  });
  function pagehide() {
    const owned = Boolean(worker || pending || loading);
    stop(owned);
    if (owned)
      status(
        "Browser decision stopped when leaving the page. Reload the local files to continue.",
      );
  }
  function teardown() {
    stop();
    window.removeEventListener("pagehide", pagehide);
    document.removeEventListener("astro:before-swap", teardown);
  }
  // A BFCache restore keeps this instance; every later pagehide must stop it.
  window.addEventListener("pagehide", pagehide);
  document.addEventListener("astro:before-swap", teardown, { once: true });
  return {
    stop,
    selected: () => provider.value === "wasm",
    ready: () => verified,
    execute: (payload: Json) => request({ action: "predict", payload }),
  };
}

function packageFiles(provider: string, files: FileList | null) {
  const selected = Array.from(files ?? []),
    names = ["manifest.json", ...decisionFiles];
  if (
    provider !== "wasm" ||
    selected.length !== names.length ||
    new Set(selected.map((file) => file.name)).size !== names.length ||
    selected.some((file) => !names.includes(file.name))
  )
    throw Error("Select WASM and all five exported package files together.");
  if (
    selected.some(
      (file) =>
        file.size < 1 ||
        file.size >
          (file.name === "model.onnx.data"
            ? 1280 * 1024 ** 2
            : file.name === "manifest.json"
              ? 8 * 1024 ** 2
              : 64 * 1024 ** 2),
    )
  )
    throw Error("A local decision file exceeds its admission limit.");
  return selected;
}
