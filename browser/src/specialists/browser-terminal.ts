/** Browser-terminal ownership, cancellation and file loading; no API requests. */
type Json = Record<string, unknown>;
export function setupBrowserTerminal(
  root: HTMLElement,
  changed: () => void,
  status: (text: string) => void,
) {
  const get = <T extends HTMLElement>(id: string) =>
    root.querySelector<T>(`#sp-${id}`)!;
  const provider = get<HTMLSelectElement>("terminal-provider");
  const file = get<HTMLInputElement>("terminal-artifact");
  let worker: Worker | undefined,
    verified = false,
    serial = 0,
    generation = 0;
  const pending = new Map<
    number,
    {
      resolve: (value: Json) => void;
      reject: (error: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();
  function stop(): void {
    generation++;
    worker?.terminate();
    worker = undefined;
    verified = false;
    for (const row of pending.values()) {
      clearTimeout(row.timer);
      row.reject(new Error("Browser terminal stopped."));
    }
    pending.clear();
    changed();
  }
  function request(payload: Json): Promise<Json> {
    return new Promise((resolve, reject) => {
      if (!worker) {
        reject(new Error("Load a terminal artifact first."));
        return;
      }
      const id = ++serial;
      const timer = setTimeout(() => {
        stop();
        status(
          "Browser inference timed out and was stopped. Reload the artifact to retry.",
        );
      }, 45_000);
      pending.set(id, { resolve, reject, timer });
      worker.postMessage({ ...payload, id });
    });
  }
  provider.addEventListener("change", () => {
    stop();
    status(
      provider.value === "python"
        ? "Python execution selected. Connect your local runtime."
        : "Browser execution selected. Load and verify a local terminal artifact.",
    );
  });
  file.addEventListener("change", () => {
    stop();
    status("Artifact selected. Load and verify it before prediction.");
  });
  get("terminal-stop").addEventListener("click", () => {
    stop();
    status("Browser terminal stopped. Your local checkpoint is unchanged.");
  });
  get("terminal-load").addEventListener("click", async () => {
    const selected = file.files?.[0];
    if (provider.value === "python") {
      status("Choose WASM or WebGPU to import a browser artifact.");
      return;
    }
    if (!selected || selected.size > 32 * 1024 ** 2) {
      status("Select an exported terminal JSON artifact up to 32 MiB.");
      return;
    }
    stop();
    const epoch = generation,
      selectedProvider = provider.value;
    worker = new Worker(new URL("./terminal-worker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (event) => {
      const row = pending.get(event.data.id);
      if (!row) return;
      clearTimeout(row.timer);
      pending.delete(event.data.id);
      if (event.data.error) row.reject(new Error(event.data.error));
      else row.resolve(event.data.result as Json);
    };
    worker.onerror = () => {
      if (epoch !== generation) return;
      stop();
      status("Browser terminal worker failed. Reload the artifact to retry.");
    };
    status("Loading local weights and checking three Python parity probes…");
    try {
      const text = await selected.text();
      if (epoch !== generation) return;
      const result = await request({
        command: "load",
        text,
        provider: selectedProvider,
      });
      if (epoch !== generation) return;
      verified = true;
      status(
        `${String(result.provider).toUpperCase()} ready · ${String(result.dtype)} · maximum logit error ${Number(result.maximum_logit_error).toExponential(2)}. Choose Predict. Model quality remains unqualified.`,
      );
      changed();
    } catch (error) {
      if (epoch !== generation) return;
      stop();
      status(String(error));
    }
  });
  window.addEventListener("pagehide", stop);
  return {
    selected: () => provider.value !== "python",
    ready: () => verified,
    execute: (payload: Json) =>
      request({
        screen: payload.screen,
        event: payload.event,
        session: payload.session,
        parallel: payload.parallel,
        command: "predict",
      }),
  };
}
