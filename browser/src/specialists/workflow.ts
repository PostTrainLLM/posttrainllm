/** Guided imports and durable local jobs. Contract: docs/factory/specialist-labs.md. */
type Json = Record<string, unknown>;
type Mode = "decision" | "forecast" | "terminal";
type Model = {
  id: string;
  mode: Mode;
  label: string;
  cached: boolean;
  ready: boolean;
  compatible: boolean;
  missing_packages: string[];
};
type Run = {
  run_id: string;
  mode: Mode;
  action: string;
  status: string;
  created_at: string;
  error?: string;
  output?: Json;
  recipe?: { payload: Json; selection: Record<Mode, string> };
  progress?: {
    phase: string;
    step: number;
    total: number;
    losses: { step: number; loss: number }[];
  };
};
type Workspace = {
  models: Model[];
  selection: Record<Mode, string>;
  active_artifacts: Record<Mode, string>;
  runs: Run[];
  artifacts: { id: string; mode: Mode; run_id: string; steps: number }[];
};
type Host = {
  request: (path: string, data?: Json) => Promise<Json>;
  mode: () => Mode;
  action: HTMLSelectElement;
  input: HTMLTextAreaElement;
  busy: () => boolean;
  setBusy: (value: boolean) => void;
  display: (body: Json) => void;
  restore: (mode: Mode, action: string, payload: Json) => void;
};

export function lossPoints(losses: { loss: number }[]): string {
  const values = losses.map((row) => row.loss);
  if (!values.length || !values.every(Number.isFinite)) return "";
  const min = Math.min(...values),
    span = Math.max(...values) - min || 1;
  return values
    .map(
      (v, i) =>
        `${10 + (i / Math.max(1, values.length - 1)) * 380},${110 - ((v - min) / span) * 100}`,
    )
    .join(" ");
}

function readinessText(selected?: Model, active?: string): string {
  if (active)
    return `Saved artifact ${active.slice(0, 8)} selected. Choose a base model to return to baseline.`;
  if (!selected)
    return "Experimental tiny model. No shell capability is established.";
  if (!selected.compatible) return "This model requires an Apple Silicon Mac.";
  if (selected.missing_packages.length)
    return `Missing runtime packages: ${selected.missing_packages.join(", ")}. Run the local setup command.`;
  return selected.ready
    ? "Cached and ready · pinned revision · loads on first use."
    : "Weights missing. Download selected model explicitly; this contacts Hugging Face.";
}

export function setupWorkflow(root: HTMLElement, host: Host) {
  const get = <T extends HTMLElement = HTMLElement>(id: string) => {
    const element = root.querySelector<T>(`#sp-${id}`);
    if (!element) throw new Error(`Missing workflow control ${id}`);
    return element;
  };
  const modelSelect = get<HTMLSelectElement>("model-select");
  const steps = get<HTMLInputElement>("steps");
  const status = get("status");
  const datasets = new Map<Mode, Json>();
  const uploads = new Map<Mode, Json>();
  let workspace: Workspace | null = null;
  let currentJob: string | null = null;
  let ceiling: unknown = null;

  function error(value: unknown): void {
    status.textContent = value instanceof Error ? value.message : String(value);
  }
  async function guarded(fn: () => Promise<void>): Promise<void> {
    try {
      await fn();
    } catch (e) {
      error(e);
    }
  }
  function button(label: string, fn: () => Promise<void>): HTMLButtonElement {
    const node = document.createElement("button");
    node.type = "button";
    node.textContent = label;
    node.addEventListener("click", () => {
      if (!host.busy()) void guarded(fn);
    });
    return node;
  }

  function modelState(): void {
    if (!workspace) return;
    const mode = host.mode();
    modelSelect.replaceChildren(
      ...workspace.models
        .filter((m) => m.mode === mode)
        .map((m) => new Option(m.label, m.id)),
    );
    modelSelect.disabled = mode === "terminal" || host.busy();
    const active = workspace.active_artifacts[mode];
    if (mode === "terminal")
      modelSelect.append(
        new Option(
          active
            ? "Saved terminal artifact"
            : "Tiny terminal · train from scratch",
          "terminal",
        ),
      );
    else modelSelect.value = workspace.selection[mode];
    if (active && mode !== "terminal") {
      modelSelect.append(
        new Option(
          `Saved ${mode} artifact · ${active.slice(0, 8)}`,
          `artifact:${active}`,
        ),
      );
      modelSelect.value = `artifact:${active}`;
    }
    const selected = workspace.models.find(
      (m) => m.id === workspace?.selection[mode],
    );
    get<HTMLButtonElement>("model-download").disabled =
      !selected ||
      selected.cached ||
      !selected.compatible ||
      !!selected.missing_packages.length ||
      host.busy();
    get("model-ready").textContent = readinessText(selected, active);
    get("model").textContent = active
      ? `Saved ${mode} artifact · ${active.slice(0, 8)}`
      : (selected?.label ?? "Tiny terminal · local");
  }

  function inputForAction(): void {
    get("job-progress").hidden = true;
    const data = datasets.get(host.mode());
    if (data?.[host.action.value])
      host.input.value = JSON.stringify(data[host.action.value], null, 2);
    get("steps-label").hidden = host.action.value !== "train";
    get("ceiling-note").hidden = host.action.value !== "ceiling";
    get("report").hidden = true;
  }

  async function refresh(): Promise<void> {
    workspace = (await host.request("workspace")) as unknown as Workspace;
    get<HTMLInputElement>("data-file").disabled = false;
    modelState();
    const history = get("history");
    history.replaceChildren();
    if (!workspace.runs.length)
      history.textContent =
        "No saved runs yet. Train a candidate to create the first checkpoint.";
    for (const run of workspace.runs) {
      const article = document.createElement("article"),
        text = document.createElement("p");
      text.textContent = `${run.mode} · ${run.action} · ${run.status} · ${new Date(run.created_at).toLocaleString()} · ${run.run_id.slice(0, 8)}`;
      article.append(text);
      if (["running", "queued"].includes(run.status))
        article.append(
          button("Follow run", async () => {
            await monitor(run.run_id);
          }),
        );
      article.append(
        button("Restore setup", async () => {
          const saved = (await host.request(
            `jobs/${run.run_id}`,
          )) as unknown as Run;
          if (!saved.recipe) return;
          const key = saved.recipe.selection?.[run.mode];
          if (key) await host.request("model/select", { model: key });
          host.restore(run.mode, run.action, saved.recipe.payload);
          if (saved.recipe.payload.steps)
            steps.value = String(saved.recipe.payload.steps);
          await refresh();
          status.textContent =
            "Saved setup restored. Review it before starting a new run.";
        }),
      );
      if (run.status === "completed")
        article.append(
          button("Open result", async () => {
            const saved = (await host.request(
              `jobs/${run.run_id}`,
            )) as unknown as Run;
            host.restore(run.mode, run.action, saved.recipe?.payload ?? {});
            if (saved.output) {
              get("job-progress").hidden = true;
              host.display(saved.output);
              showReport(saved.output, run.run_id);
            }
          }),
        );
      const artifact = workspace.artifacts.find((a) => a.run_id === run.run_id);
      if (artifact)
        article.append(
          button("Use saved model", async () => {
            await host.request("artifact/use", { artifact: artifact.id });
            host.restore(artifact.mode, "predict", {});
            await refresh();
            status.textContent =
              "Saved model selected. Run a prediction to use its checkpoint.";
          }),
        );
      history.append(article);
    }
  }

  function showReport(output: Json, key: string): void {
    const result = output.result as Json | undefined;
    const comparison = result?.comparison as
      | {
          metric: string;
          sample_size: number;
          regression_size: number;
          baseline: {
            primary: Record<string, number>;
            regression: Record<string, number>;
          };
          candidate: {
            primary: Record<string, number>;
            regression: Record<string, number>;
          };
        }
      | undefined;
    if (!comparison) return;
    const panel = get("report");
    panel.hidden = false;
    panel.replaceChildren();
    const heading = document.createElement("h4");
    heading.textContent = "Before / after · held-out data";
    const table = document.createElement("table");
    const header = table.createTHead().insertRow();
    for (const label of ["Slice", "Base", "Trained", "Delta"]) {
      const th = document.createElement("th");
      th.textContent = label;
      header.append(th);
    }
    const body = table.createTBody(),
      metric = comparison.metric;
    for (const slice of ["primary", "regression"] as const) {
      const row = body.insertRow(),
        sign = metric === "negative_mae" ? -1 : 1,
        before = comparison.baseline[slice][metric] * sign,
        after = comparison.candidate[slice][metric] * sign;
      for (const value of [
        slice,
        before.toFixed(4),
        after.toFixed(4),
        (after - before).toFixed(4),
      ])
        row.insertCell().textContent = value;
    }
    const note = document.createElement("p");
    note.className = "sp-note";
    note.textContent = `${metric === "negative_mae" ? "MAE · lower is better" : "Accuracy · higher is better"}. ${comparison.sample_size} primary and ${comparison.regression_size} regression observations. Report-only; this does not qualify general model quality.`;
    panel.append(heading, table, note);
    for (const [filename, label] of [
      ["report-card.html", "Open full report"],
      ["report-card.json", "Export report JSON"],
    ]) {
      const link = document.createElement("a");
      link.href = `/api/specialists/jobs/${key}/${filename}`;
      link.textContent = label;
      link.target = "_blank";
      link.rel = "noopener";
      if (filename.endsWith(".json")) link.download = filename;
      panel.append(link);
    }
  }

  async function monitor(key: string): Promise<void> {
    if (currentJob && currentJob !== key) return;
    currentJob = key;
    host.setBusy(true);
    get("job-progress").hidden = false;
    get<HTMLButtonElement>("cancel").disabled = false;
    get("cancel").hidden = false;
    try {
      while (currentJob === key) {
        const run = (await host.request(`jobs/${key}`)) as unknown as Run;
        const progress = run.progress;
        get("progress-text").textContent = progress
          ? `${progress.phase} · ${progress.step}/${progress.total || "…"}`
          : `${run.status} · loading model`;
        const bar = get<HTMLProgressElement>("progress");
        if (progress?.total) {
          bar.max = progress.total;
          bar.value = progress.step;
        } else bar.removeAttribute("value");
        const points = lossPoints(progress?.losses ?? []),
          chart = get("loss-chart");
        chart.replaceChildren();
        if (points) {
          const svg = document.createElementNS(
              "http://www.w3.org/2000/svg",
              "svg",
            ),
            line = document.createElementNS(svg.namespaceURI, "polyline");
          svg.setAttribute("viewBox", "0 0 400 120");
          svg.setAttribute("role", "img");
          svg.setAttribute("aria-label", "Observed training loss");
          line.setAttribute("points", points);
          line.setAttribute("fill", "none");
          line.setAttribute("stroke", "#48e5c2");
          svg.append(line);
          chart.append(svg);
        }
        if (!["running", "queued"].includes(run.status)) {
          if (run.status === "completed" && run.output) {
            host.display(run.output);
            showReport(run.output, key);
            const result = run.output.result as Json;
            if (result?.ceiling) ceiling = result.ceiling;
          } else status.textContent = run.error ?? `Run ${run.status}.`;
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    } finally {
      currentJob = null;
      host.setBusy(false);
      get<HTMLButtonElement>("cancel").disabled = true;
      get("cancel").hidden = true;
      await refresh();
    }
  }

  async function execute(payload: Json): Promise<void> {
    if (host.action.value === "train")
      payload = { ...payload, steps: Number(steps.value) };
    if (
      host.action.value === "compare" &&
      host.mode() === "decision" &&
      ceiling &&
      !payload.ceiling
    )
      payload = { ...payload, ceiling };
    const job = (await host.request("jobs/start", {
      mode: host.mode(),
      action: host.action.value,
      input: payload,
    })) as unknown as Run;
    await monitor(job.run_id);
  }

  get("cancel").addEventListener("click", () => {
    if (currentJob)
      void guarded(async () => {
        await host.request("jobs/cancel", { run_id: currentJob });
      });
  });
  get("refresh-runs").addEventListener("click", () => {
    void guarded(refresh);
  });
  modelSelect.addEventListener("change", () => {
    void guarded(async () => {
      if (host.busy()) return;
      if (modelSelect.value.startsWith("artifact:"))
        await host.request("artifact/use", {
          artifact: modelSelect.value.slice(9),
        });
      else await host.request("model/select", { model: modelSelect.value });
      await refresh();
    });
  });
  get("model-download").addEventListener("click", () => {
    void guarded(async () => {
      if (host.busy()) return;
      const job = (await host.request("jobs/start", {
        mode: "model",
        action: "download",
        input: { model: workspace?.selection[host.mode()] },
      })) as unknown as Run;
      await monitor(job.run_id);
    });
  });
  function configureMapping(columns: string[]): void {
    for (const name of ["question", "answer", "options", "time", "values"]) {
      const select = get<HTMLSelectElement>(`map-${name}`);
      select.replaceChildren(
        ...(name === "time"
          ? [new Option("Row order (already chronological)", "")]
          : []),
        ...columns.map((c) => new Option(c, c)),
      );
      for (const option of [...select.options]) {
        if (name === "options")
          option.selected = /^[A-Z]$|^option[_ -]/i.test(option.value);
        if (name === "values")
          option.selected = /^(value|target|sales|y)$/i.test(option.value);
      }
      const preferred = columns.find((c) =>
        name === "question"
          ? /^(question|prompt)$/i.test(c)
          : name === "answer"
            ? /^(answer|label)$/i.test(c)
            : name === "time" && /^(time|timestamp|date)$/i.test(c),
      );
      if (preferred) select.value = preferred;
    }
  }

  function renderPreview(columns: string[], records: Json[]): void {
    const table = document.createElement("table"),
      head = table.createTHead().insertRow();
    for (const column of columns) {
      const cell = document.createElement("th");
      cell.textContent = column;
      head.append(cell);
    }
    const body = table.createTBody();
    for (const record of records) {
      const row = body.insertRow();
      for (const column of columns)
        row.insertCell().textContent =
          typeof record[column] === "object"
            ? JSON.stringify(record[column])
            : String(record[column] ?? "");
    }
    get("data-preview").replaceChildren(table);
  }

  get<HTMLInputElement>("data-file").addEventListener("change", (event) => {
    void guarded(async () => {
      const file = (event.target as HTMLInputElement).files?.[0];
      if (!file) return;
      if (file.size > 800000)
        throw new Error("Import a dataset no larger than 800 KB.");
      const format = file.name.toLowerCase().split(".").at(-1) ?? "";
      const upload = { content: await file.text(), format };
      const preview = await host.request("data/inspect", upload);
      uploads.set(host.mode(), upload);
      const columns = preview.columns as string[];
      configureMapping(columns);
      get("data-mapping").hidden = false;
      renderPreview(columns, preview.preview as Json[]);
      get("data-summary").textContent =
        `${preview.count} records found. Review the mapping, then validate.`;
      mappingVisibility();
    });
  });
  get("data-apply").addEventListener("click", () => {
    void guarded(async () => {
      const upload = uploads.get(host.mode());
      if (!upload) return;
      const selected = (name: string) =>
        [...get<HTMLSelectElement>(`map-${name}`).selectedOptions].map(
          (o) => o.value,
        );
      const mapping = {
        question: get<HTMLSelectElement>("map-question").value,
        answer: get<HTMLSelectElement>("map-answer").value,
        options: selected("options"),
        timestamp: get<HTMLSelectElement>("map-time").value,
        values: selected("values"),
      };
      const result = await host.request("data/inspect", {
        ...upload,
        mode: host.mode(),
        mapping,
        horizon: Number(get<HTMLInputElement>("horizon").value),
      });
      const dataset = result.dataset as Json;
      datasets.set(host.mode(), dataset);
      ceiling = null;
      get("data-summary").textContent =
        `${String(dataset.summary)} · frozen data ${String(result.sha256).slice(0, 12)}`;
      inputForAction();
      get<HTMLDetailsElement>("import-panel").open = false;
      status.textContent =
        "Dataset validated. Choose training, then compare on its held-out splits.";
    });
  });
  function mappingVisibility(): void {
    root.querySelectorAll<HTMLElement>("[data-sp-map]").forEach((el) => {
      el.hidden = el.dataset.spMap !== host.mode();
    });
  }
  return {
    execute,
    refresh,
    inputForAction,
    async connect() {
      await refresh();
      const running = workspace?.runs.find((r) =>
        ["running", "queued"].includes(r.status),
      );
      if (running) await monitor(running.run_id);
    },
    modeChanged() {
      steps.value = host.mode() === "terminal" ? "200" : "1";
      get("data-mapping").hidden = !uploads.has(host.mode());
      get("data-summary").textContent = String(
        datasets.get(host.mode())?.summary ??
          "Import and validate a dataset, or use the built-in example.",
      );
      modelState();
      mappingVisibility();
      inputForAction();
    },
    reset() {
      datasets.delete(host.mode());
      inputForAction();
    },
  };
}
