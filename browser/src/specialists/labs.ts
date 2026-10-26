import { setupBrowserForecast } from "./browser-forecast";
/** Local specialist modes inside /playground. No network calls before Connect. */
import { setupWorkflow } from "./workflow";
import { setupBrowserTerminal } from "./browser-terminal";

type Mode = "decision" | "forecast" | "terminal";
type Json = Record<string, unknown>;

const modes: Record<
  Mode,
  {
    title: string;
    description: string;
    model: string;
    actions: Record<string, string>;
  }
> = {
  decision: {
    title: "Make a choice in one forward pass.",
    description:
      "Compare every allowed answer. Fit temperature on separate examples before interpreting the probabilities.",
    model: "Qwen3 · 1.7B · local",
    actions: {
      predict: "Predict an answer",
      score: "Score a dataset",
      prepare: "Prepare four frozen splits",
      train: "Train a LoRA adapter",
      calibrate: "Fit temperature",
      eval: "Evaluate with frontier ceiling",
      ceiling: "Validate benchmark with Codex",
      compare: "Compare trained model with baseline",
    },
  },
  forecast: {
    title: "Forecast related series together.",
    description:
      "Predict a distribution with Timestral. Known-future inputs can help; future targets stay out of the context.",
    model: "Timestral · local CPU",
    actions: {
      predict: "Forecast quantiles",
      synthetic: "Generate a synthetic series",
      train: "Adapt with pinball loss",
      backtest: "Run a chronological backtest",
      compare: "Compare trained model with baseline",
    },
  },
  terminal: {
    title: "Predict the screen after each key.",
    description:
      "A learned world of characters, rows, and cursor movements. Inspect the delta or verify a parallel draft.",
    model: "Your terminal artifact · local",
    actions: {
      predict: "Predict a screen update",
      train: "Train a terminal model",
      eval: "Evaluate with frontier ceiling",
    },
  },
};

export function sampleInput(mode: Mode, action: string): Json {
  const workflowSamples: Record<string, Json> = {
    compare: {},
    ceiling: { rows: [] },
  };
  if (action in workflowSamples) return workflowSamples[action];
  const item = {
    id: "example-even",
    question: "Which integer is even?",
    options: { A: "3", B: "8", C: "7", D: "9" },
  };
  if (mode === "decision") {
    if (action === "predict") return { item, threshold: 0 };
    if (action === "score") return { rows: [{ ...item, answer: "B" }] };
    if (action === "train")
      return { rows: [{ ...item, answer: "B" }], steps: 1 };
    if (action === "prepare")
      return {
        rows: Array.from({ length: 20 }, (_, i) => ({
          id: `parity-${i}`,
          question: `Is ${i} even or odd?`,
          options: { A: "Even", B: "Odd" },
          answer: i % 2 ? "B" : "A",
        })),
      };
    if (action === "calibrate") return { scores: [], excluded: [] };
    return { scores: [], ceiling: {}, baseline: [] };
  }
  if (mode === "forecast") {
    if (action === "synthetic") return { seed: 7, length: 128 };
    const values = Array.from(
      { length: 128 },
      (_, i) =>
        Math.round((Math.sin((i * Math.PI) / 12) + i * 0.002) * 1000) / 1000,
    );
    const schedule = Array.from({ length: 128 }, (_, i) =>
      i % 24 < 12 ? 1 : 0,
    );
    const series = {
      id: "synthetic-example",
      values: [values, values.map((v, i) => v * 0.5 + schedule[i])],
      known_covariates: [schedule],
    };
    const context = {
      id: series.id,
      context: series.values.map((row) => row.slice(0, 80)),
      known_covariates: [schedule.slice(0, 104)],
    };
    if (action === "predict") return { item: context, horizon: 24 };
    if (action === "train")
      return {
        rows: [
          {
            ...context,
            target: series.values.map((row) => row.slice(80, 104)),
          },
        ],
        steps: 1,
      };
    return { series, horizon: 24, origins: [80, 104], season: 24 };
  }
  const screen = {
    lines: ["lab$        ", "            "],
    cursor_row: 0,
    cursor_col: 5,
    visible: true,
  };
  if (action === "predict")
    return { screen, event: { keys: [97] }, parallel: false };
  if (action === "eval") return { episodes: [], ceiling: {} };
  const frames = Array.from("abcd", (character, index) => ({
    event: { keys: [character.charCodeAt(0)] },
    screen: {
      ...screen,
      lines: [`lab$ ${"abcd".slice(0, index + 1)}`.padEnd(12), "            "],
      cursor_col: 6 + index,
    },
  }));
  return {
    episodes: [0, 1].map((i) => ({
      id: `tiny-typing-${i}`,
      initial_screen: screen,
      frames,
    })),
    steps: 200,
  };
}

export function keyBytes(
  event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey">,
): number[] | null {
  if (event.metaKey) return null;
  const controls: Record<string, number[]> = {
    Enter: [13],
    Backspace: [127],
    Escape: [27],
    Tab: [9],
    ArrowUp: [27, 91, 65],
    ArrowDown: [27, 91, 66],
    ArrowRight: [27, 91, 67],
    ArrowLeft: [27, 91, 68],
    Delete: [27, 91, 51, 126],
  };
  let bytes = controls[event.key];
  if (
    !bytes &&
    event.key.length === 1 &&
    event.key.charCodeAt(0) >= 32 &&
    event.key.charCodeAt(0) <= 126
  )
    bytes = [
      event.ctrlKey
        ? event.key.toUpperCase().charCodeAt(0) & 31
        : event.key.charCodeAt(0),
    ];
  if (!bytes) return null;
  return event.altKey ? [27, ...bytes] : bytes;
}

function object(value: unknown): Json {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Expected a JSON object.");
  return value as Json;
}

function formatMeasurements(measurements: Json): string {
  const parts = [`${Number(measurements.elapsed_seconds).toFixed(2)} s`];
  if (typeof measurements.process_peak_rss_bytes === "number")
    parts.push(
      `${(measurements.process_peak_rss_bytes / 2 ** 20).toFixed(0)} MiB process peak`,
    );
  parts.push("$0 paid API");
  return parts.join(" · ");
}

export function setupSpecialistLabs(): void {
  const root = document.querySelector<HTMLElement>("#specialists");
  if (!root) return;
  const get = <T extends HTMLElement>(id: string): T => {
    const element = root.querySelector<T>(`#sp-${id}`);
    if (!element) throw new Error(`Missing specialist control: ${id}`);
    return element;
  };
  const input = get<HTMLTextAreaElement>("input"),
    action = get<HTMLSelectElement>("action"),
    run = get<HTMLButtonElement>("run"),
    status = get("status"),
    visual = get("visual"),
    form = get<HTMLFormElement>("form");
  const tabs = [...root.querySelectorAll<HTMLButtonElement>("[data-sp-mode]")];
  const saved = new Map<Mode, { action: string; text: string }>();
  let mode: Mode = "decision",
    connected = false,
    busy = false,
    lastOutput: unknown = null,
    artifact: string | null = null,
    session: string | undefined;
  let keyQueue = Promise.resolve();
  let executionGeneration = 0;
  let workflow: ReturnType<typeof setupWorkflow> | undefined;
  const portable = setupBrowserTerminal(
    root,
    () => resetExecution(),
    (text) => status.replaceChildren(text),
  );
  const portableForecast = setupBrowserForecast(
    root,
    () => {
      resetExecution();
      if (mode === "forecast" && portableForecast.selected())
        get<HTMLDetailsElement>("connect-help").open = false;
      else workflow?.modeChanged();
    },
    (text) => status.replaceChildren(text),
    (value) => {
      if (busy || mode !== "forecast") return;
      action.value = "predict";
      input.value = JSON.stringify(value, null, 2);
      resetOutput();
      resetExecution();
    },
  );
  const browserRuntime = () =>
    mode === "forecast" ? portableForecast : portable;
  const inBrowser = () =>
    (mode === "terminal" || mode === "forecast") && browserRuntime().selected();

  function resetExecution(): void {
    session = undefined;
    executionGeneration++;
    setBusy(busy);
  }

  async function request(path: string, data?: Json): Promise<Json> {
    if (location.hostname !== "127.0.0.1")
      throw new Error(
        "Open the local lab served by lab.py serve before importing private data.",
      );
    const response = await fetch(
      `/api/specialists/${path}`,
      data
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }
        : { cache: "no-store" },
    );
    if (
      !(response.headers.get("Content-Type") ?? "").includes("application/json")
    )
      throw new Error(
        "Open the local lab served by lab.py serve, then connect again.",
      );
    const body = object(await response.json());
    if (!response.ok)
      throw new Error(
        typeof body.error === "string" ? body.error : "Local operation failed.",
      );
    return body;
  }

  function setBusy(value: boolean): void {
    busy = value;
    const browserForecast = mode === "forecast" && portableForecast.selected();
    get("model-picker").hidden = browserForecast;
    get("history-panel").hidden = browserForecast;
    get("connection").textContent = browserForecast
      ? "Browser execution · local files"
      : connected
        ? "Runtime connected · local"
        : "Runtime disconnected";
    if (browserForecast || !connected)
      get("model").textContent = browserForecast
        ? "Timestral · browser WASM"
        : modes[mode].model;
    form.setAttribute("aria-busy", String(value));
    run.disabled =
      value ||
      (inBrowser()
        ? !browserRuntime().ready() || action.value !== "predict"
        : !connected);
    run.textContent = value
      ? "Running locally…"
      : inBrowser()
        ? "Predict in this tab →"
        : "Run locally →";
    for (const tab of tabs) tab.disabled = value;
    action.disabled = value;
  }

  function resetOutput(): void {
    root!.dataset.hasResult = "false";
    visual.replaceChildren();
    get("terminal-controls").hidden = true;
    get("inspector").hidden = true;
    get<HTMLButtonElement>("export").disabled = true;
    get("use-artifact").hidden = true;
    get("measurements").textContent = "";
    artifact = null;
    lastOutput = null;
  }

  function selectMode(next: Mode): void {
    if (busy) return;
    if (mode === "forecast" && next !== mode) portableForecast.stop();
    resetExecution();
    if (action.value)
      saved.set(mode, { action: action.value, text: input.value });
    mode = next;
    get("terminal-browser").hidden = mode !== "terminal";
    get("forecast-browser").hidden = mode !== "forecast";
    const config = modes[mode];
    get("mode-title").textContent = config.title;
    get("mode-description").textContent = config.description;
    get("model").textContent = config.model;
    action.replaceChildren(
      ...Object.entries(config.actions).map(
        ([value, label]) => new Option(label, value),
      ),
    );
    const draft = saved.get(mode);
    if (draft) {
      action.value = draft.action;
      input.value = draft.text;
    } else
      input.value = JSON.stringify(sampleInput(mode, action.value), null, 2);
    for (const tab of tabs) {
      const selected = tab.dataset.spMode === mode;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    }
    get("workspace").setAttribute("aria-labelledby", `sp-tab-${mode}`);
    resetOutput();
    status.textContent = inBrowser()
      ? browserRuntime().ready()
        ? "Browser runtime ready. Edit the example and predict in this tab."
        : "Load and verify a browser artifact before prediction."
      : connected
        ? "Ready. Edit the example and run locally."
        : "Connect your local runtime to run this example.";
    workflow?.modeChanged();
    setBusy(false);
  }

  function display(body: Json): void {
    root!.dataset.hasResult = "true";
    lastOutput = body;
    const result = object(body.result ?? body);
    visual.replaceChildren();
    get("output").textContent = JSON.stringify(body, null, 2);
    get("inspector").hidden = false;
    get<HTMLButtonElement>("export").disabled = false;
    artifact = typeof result.artifact === "string" ? result.artifact : null;
    get("use-artifact").hidden = !artifact || action.value === "prepare";
    const measurements = body.measurements ? object(body.measurements) : null;
    get("measurements").textContent = measurements
      ? formatMeasurements(measurements)
      : "";
    if (Array.isArray(result.predictions) && result.predictions.length) {
      const prediction = object(result.predictions[0]);
      status.textContent = `Selected ${prediction.label ?? "abstain"}. ${String(prediction.calibration)}.`;
      for (const [label, raw] of Object.entries(
        object(prediction.probabilities),
      )) {
        const probability = Number(raw);
        const row = document.createElement("div");
        row.className = "sp-probability";
        const caption = document.createElement("div");
        caption.className = "sp-probability-label";
        const name = document.createElement("span"),
          value = document.createElement("span");
        name.textContent = label;
        value.textContent = `${(probability * 100).toFixed(2)}%`;
        caption.append(name, value);
        const track = document.createElement("div"),
          fill = document.createElement("div");
        track.className = "sp-probability-track";
        fill.className = "sp-probability-fill";
        fill.style.width = `${Math.min(1, Math.max(0, probability)) * 100}%`;
        track.append(fill);
        row.append(caption, track);
        visual.append(row);
      }
    } else if (
      Array.isArray(result.quantiles) &&
      Array.isArray(result.quantile_levels)
    ) {
      drawForecast(visual, result);
      status.textContent =
        "Forecast complete. First target shown: median and outer quantiles. Model quality remains unqualified.";
    } else if (result.screen) {
      const screen = object(result.screen);
      const pre = document.createElement("pre");
      pre.setAttribute("aria-label", "Predicted terminal screen");
      (screen.lines as string[]).forEach((line, row) => {
        if (row) pre.append("\n");
        if (screen.visible && row === screen.cursor_row) {
          const column = Number(screen.cursor_col);
          pre.append(line.slice(0, column));
          const cursor = document.createElement("span");
          cursor.textContent = line[column] ?? " ";
          cursor.style.background = "#48e5c2";
          cursor.style.color = "#08231c";
          cursor.setAttribute("aria-label", "cursor");
          pre.append(cursor, line.slice(column + 1));
        } else pre.append(line);
      });
      visual.append(pre);
      session = typeof result.session === "string" ? result.session : undefined;
      get("terminal-controls").hidden = false;
      status.textContent = `Screen predicted · ${Array.isArray(result.tokens) ? result.tokens.length : 0} delta tokens · ${Number(result.context_resets ?? 0)} context resets.`;
    } else
      status.textContent = artifact
        ? "Artifact saved locally. Inspect its metadata before using it."
        : "Operation complete. Inspect or export the full output.";
    status.scrollIntoView({ block: "nearest" });
  }

  async function perform(payload: Json): Promise<Json | undefined> {
    if (inBrowser()) {
      if (action.value !== "predict")
        throw new Error(
          "Browser execution supports prediction. Select Python for training and qualification.",
        );
      return browserRuntime().execute(payload);
    }
    if (["train", "compare", "ceiling"].includes(action.value)) {
      await workflow?.execute(payload);
      return;
    }
    return request(`${mode}/${action.value}`, payload);
  }

  async function execute(payload?: Json): Promise<void> {
    if ((!connected && !inBrowser()) || busy) return;
    const generation = executionGeneration;
    setBusy(true);
    status.textContent = "Running locally…";
    try {
      const result = await perform(payload ?? object(JSON.parse(input.value)));
      if (result && generation === executionGeneration) display(result);
    } catch (error) {
      if (generation === executionGeneration)
        status.textContent =
          error instanceof Error ? error.message : "Operation failed.";
    } finally {
      setBusy(false);
    }
  }

  get("connect").addEventListener("click", async () => {
    if (location.hostname !== "127.0.0.1") {
      status.textContent =
        "Start the runtime, then use Open local lab. This page connects only from the local runtime's own origin.";
      return;
    }
    try {
      await request("health");
      connected = true;
      get("connection").textContent = "Runtime connected · local";
      get<HTMLDetailsElement>("connect-help").open = false;
      status.textContent =
        "Connected. Cached models load on their first operation.";
      setBusy(false);
      await workflow?.connect();
    } catch (error) {
      connected = false;
      setBusy(false);
      status.textContent =
        error instanceof Error ? error.message : "Runtime unavailable.";
    }
  });
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectMode(tab.dataset.spMode as Mode));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? tabs.length - 1
            : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
              tabs.length;
      tabs[next].click();
      tabs[next].focus();
    });
  });
  action.addEventListener("change", () => {
    input.value = JSON.stringify(sampleInput(mode, action.value), null, 2);
    resetOutput();
    resetExecution();
    workflow?.inputForAction();
    setBusy(false);
  });
  get("example").addEventListener("click", () => {
    workflow?.reset();
    input.value = JSON.stringify(sampleInput(mode, action.value), null, 2);
    resetExecution();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void execute();
  });
  get<HTMLInputElement>("file").addEventListener("change", async (event) => {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 1024 * 1024) {
      status.textContent = "Import a JSON file no larger than 1 MiB.";
      return;
    }
    try {
      const raw = await file.text();
      const data: unknown = file.name.endsWith(".jsonl")
        ? {
            rows: raw
              .split(/\r?\n/)
              .filter((line) => line.trim())
              .map((line) => JSON.parse(line) as unknown),
          }
        : JSON.parse(raw);
      input.value = JSON.stringify(object(data), null, 2);
      resetExecution();
    } catch {
      status.textContent =
        "This file is not valid input JSON. Check the example's structure.";
    }
  });
  get("export").addEventListener("click", () => {
    if (!lastOutput) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(lastOutput, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${mode}-${action.value}-result.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  get("use-artifact").addEventListener("click", async () => {
    if (!artifact || busy) return;
    setBusy(true);
    try {
      const active = await request("artifact/use", { artifact });
      status.textContent = `${String(active.mode)} artifact loaded. Choose prediction to try it; quality remains unqualified.`;
      resetExecution();
      await workflow?.refresh();
    } catch (error) {
      status.textContent = String(error);
    } finally {
      setBusy(false);
    }
  });

  function enqueue(event: Json): void {
    const generation = executionGeneration;
    keyQueue = keyQueue
      .then(async () => {
        if (
          generation !== executionGeneration ||
          mode !== "terminal" ||
          action.value !== "predict"
        )
          return;
        const payload = object(JSON.parse(input.value));
        if (session) payload.session = session;
        payload.event = event;
        await execute(payload);
      })
      .catch((error) => {
        status.textContent = String(error);
      });
  }
  const terminalInput = get<HTMLInputElement>("terminal-input");
  terminalInput.addEventListener("keydown", (event) => {
    const bytes = keyBytes(event);
    if (!bytes) return;
    event.preventDefault();
    enqueue({ keys: bytes });
  });
  terminalInput.addEventListener("input", () => {
    const text = terminalInput.value;
    terminalInput.value = "";
    if (text && /^[\x20-\x7e]{1,256}$/.test(text))
      enqueue({ keys: [...text].map((c) => c.charCodeAt(0)) });
    else if (text)
      status.textContent =
        "Use 1–256 printable ASCII characters for this terminal codec.";
  });
  terminalInput.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text") ?? "";
    if (!text || text.length > 256 || /[^\x09\x0a\x0d\x20-\x7e]/.test(text)) {
      status.textContent = "Paste up to 256 ASCII characters.";
      return;
    }
    enqueue({
      keys: [...text.replace(/\r?\n/g, "\r")].map((c) => c.charCodeAt(0)),
    });
  });
  root.querySelectorAll<HTMLButtonElement>("[data-sp-key]").forEach((button) =>
    button.addEventListener("click", () => {
      const key = button.dataset.spKey;
      enqueue(
        key === "wait"
          ? { wait_ms: 1000 }
          : {
              keys: key === "enter" ? [13] : key === "backspace" ? [127] : [27],
            },
      );
    }),
  );
  get("reset-session").addEventListener("click", () => {
    resetExecution();
    status.textContent =
      "Session reset. The next key starts from your input screen.";
  });
  input.addEventListener("change", () => {
    resetExecution();
  });
  workflow = setupWorkflow(root, {
    request,
    mode: () => mode,
    action,
    input,
    busy: () => busy,
    setBusy,
    display,
    restore(next, operation, payload) {
      selectMode(next);
      action.value = operation;
      workflow?.inputForAction();
      input.value = Object.keys(payload).length
        ? JSON.stringify(payload, null, 2)
        : JSON.stringify(sampleInput(next, operation), null, 2);
      get<HTMLDetailsElement>("advanced").open = true;
    },
  });
  selectMode("decision");
}

function drawForecast(container: HTMLElement, result: Json): void {
  const all = result.quantiles as number[][][];
  const levels = result.quantile_levels as number[];
  const first = all[0];
  if (!first?.length || !levels.includes(0.5)) return;
  const values = first.flat();
  if (!values.every(Number.isFinite)) return;
  const low = Math.min(...values),
    high = Math.max(...values),
    span = high - low || 1;
  const point = (index: number, value: number) =>
    `${12 + (index / Math.max(1, first.length - 1)) * 376},${168 - ((value - low) / span) * 150}`;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 400 185");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "First target forecast: median with outer quantile interval",
  );
  const band = document.createElementNS(svg.namespaceURI, "polygon");
  band.setAttribute(
    "points",
    [
      ...first.map((row, i) => point(i, row[0])),
      ...first.map((row, i) => point(i, row[row.length - 1])).reverse(),
    ].join(" "),
  );
  band.setAttribute("fill", "#48e5c21a");
  svg.append(band);
  const line = document.createElementNS(svg.namespaceURI, "polyline");
  line.setAttribute(
    "points",
    first.map((row, i) => point(i, row[levels.indexOf(0.5)])).join(" "),
  );
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#48e5c2");
  line.setAttribute("stroke-width", "2");
  svg.append(line);
  container.append(svg);
}
