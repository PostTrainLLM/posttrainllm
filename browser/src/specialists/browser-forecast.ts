/** Own one cancellable forecasting worker and activate only verified local artifacts. */
import { object, type Json } from "./forecast-input";
export function setupBrowserForecast(
  root: HTMLElement,
  changed: () => void,
  status: (text: string) => void,
  example: (value: Json) => void,
) {
  const get = <T extends HTMLElement>(id: string) =>
    root.querySelector<T>(`#sp-forecast-${id}`)!;
  const provider = get<HTMLSelectElement>("provider"),
    model = get<HTMLInputElement>("model"),
    manifest = get<HTMLInputElement>("manifest");
  const useExample = get<HTMLButtonElement>("example");
  let worker: Worker | undefined,
    verified = false,
    generation = 0,
    serial = 0,
    sample: Json | undefined;
  let pending:
    | {
        id: number;
        resolve: (result: Json) => void;
        reject: (error: Error) => void;
        timer: ReturnType<typeof setTimeout>;
      }
    | undefined;
  function stop() {
    generation++;
    verified = false;
    sample = undefined;
    useExample.disabled = true;
    worker?.terminate();
    worker = undefined;
    if (pending) {
      clearTimeout(pending.timer);
      pending.reject(Error("Browser forecast stopped."));
      pending = undefined;
    }
    changed();
  }
  function request(
    payload: Json,
    transfer: Transferable[] = [],
  ): Promise<Json> {
    if (!worker || pending)
      return Promise.reject(
        Error("Load an artifact and wait for the current operation."),
      );
    return new Promise((resolve, reject) => {
      const id = ++serial;
      const timer = setTimeout(() => {
        stop();
        status(
          "Browser forecast exceeded the 45-second execution budget and was stopped. Load the artifact again to retry; if it keeps timing out, use a smaller fixed-shape export.",
        );
      }, 45_000);
      pending = { id, resolve, reject, timer };
      try {
        worker!.postMessage({ ...payload, id }, transfer);
      } catch (error) {
        clearTimeout(timer);
        pending = undefined;
        reject(
          error instanceof Error
            ? error
            : Error("Could not send forecast input."),
        );
      }
    });
  }
  provider.addEventListener("change", () => {
    stop();
    status(
      provider.value === "python"
        ? "Python forecasting selected. Connect your local runtime."
        : "Browser forecasting selected. Load a matching manifest and model.",
    );
  });
  for (const file of [model, manifest])
    file.addEventListener("change", () => {
      stop();
      status("Forecast files selected. Load and verify before prediction.");
    });
  get("stop").addEventListener("click", () => {
    stop();
    status("Browser forecast stopped.");
  });
  useExample.addEventListener("click", () => {
    if (sample) example(sample);
  });
  get("load").addEventListener("click", async () => {
    stop();
    const epoch = generation;
    const weights = model.files?.[0],
      receipt = manifest.files?.[0];
    if (
      provider.value !== "wasm" ||
      !weights ||
      !receipt ||
      weights.size > 1024 ** 3 ||
      receipt.size > 64 * 1024 ** 2
    ) {
      status(
        "Choose WASM and select model.onnx (up to 1 GiB) plus manifest.json (up to 64 MiB).",
      );
      return;
    }
    status("Loading local forecast files and checking three Python probes…");
    try {
      const [bytes, text] = await Promise.all([
        weights.arrayBuffer(),
        receipt.text(),
      ]);
      if (epoch !== generation) return;
      worker = new Worker(new URL("./forecast-worker.ts", import.meta.url), {
        type: "module",
      });
      worker.onmessage = (event: MessageEvent<Json>) => {
        if (epoch !== generation || !pending || event.data.id !== pending.id)
          return;
        const current = pending;
        pending = undefined;
        clearTimeout(current.timer);
        if (event.data.error) current.reject(Error(String(event.data.error)));
        else current.resolve(object(event.data.result));
      };
      worker.onerror = () => {
        if (epoch === generation) {
          stop();
          status("Browser forecast worker failed and was stopped.");
        }
      };
      const result = await request(
        { action: "load", model: bytes, manifest: text },
        [bytes],
      );
      if (epoch !== generation) return;
      verified = true;
      sample = object(result.example);
      useExample.disabled = false;
      changed();
      const shape = object(result.shape);
      status(
        `Browser forecast ready. ${shape.targets} targets × ${shape.context} history steps → ${shape.horizon} forecast steps. Use the artifact example or matching input. Quality remains unqualified.`,
      );
    } catch (error) {
      if (epoch === generation) {
        stop();
        status(
          error instanceof Error
            ? error.message
            : "Forecast artifact loading failed.",
        );
      }
    }
  });
  function teardown() {
    stop();
    window.removeEventListener("pagehide", stop);
    document.removeEventListener("astro:before-swap", teardown);
  }
  // A BFCache restore keeps this instance; every later pagehide must stop it.
  window.addEventListener("pagehide", stop);
  document.addEventListener("astro:before-swap", teardown, { once: true });
  return {
    stop,
    selected: () => provider.value === "wasm",
    ready: () => verified,
    execute: (payload: Json) => request({ action: "predict", payload }),
  };
}
