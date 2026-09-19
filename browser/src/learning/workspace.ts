import {
  applyCheckpoint,
  completeRecall,
  createCheckpoint,
  dueRecalls,
  emptyLearningState,
  loadLearningState,
  makeBackup,
  mergeLearningState,
  parseBackup,
  saveLearningState,
  selectLearningModule,
  type LearningBackup,
  type RecallCheck,
} from "./state";
import type { LearningUnit } from "./content";

const root = document.querySelector<HTMLElement>("[data-learning-workspace]");

if (root) {
  const unitsElement = document.querySelector<HTMLScriptElement>(
    "#learning-units-data",
  );
  const units = unitsElement
    ? (JSON.parse(unitsElement.textContent ?? "[]") as LearningUnit[])
    : [];
  const fields = {
    actualWork: root.querySelector<HTMLTextAreaElement>("#actual-work"),
    explanation: root.querySelector<HTMLTextAreaElement>("#explanation"),
    repoConnection: root.querySelector<HTMLInputElement>("#repo-connection"),
    openQuestions: root.querySelector<HTMLTextAreaElement>("#open-questions"),
  };
  const status = root.querySelector<HTMLElement>("[data-save-status]");
  const stateLabel = root.querySelector<HTMLElement>("[data-learning-status]");
  const recallRegion = root.querySelector<HTMLElement>("[data-recall-region]");
  const historyRegion = root.querySelector<HTMLElement>(
    "[data-history-region]",
  );
  const importInput = root.querySelector<HTMLInputElement>("#learning-import");
  let state = emptyLearningState();
  let pendingImport: LearningBackup | null = null;
  let saveTimer: number | undefined;

  const setMessage = (
    message: string,
    kind: "ok" | "error" | "quiet" = "quiet",
  ) => {
    if (!status) return;
    status.textContent = message;
    status.dataset.kind = kind;
  };

  const escapeHtml = (value: string) =>
    value.replace(
      /[&<>"]/g,
      (character) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[
          character
        ] ?? character,
    );

  const currentUnit = () =>
    units.find((unit) => unit.id === state.currentModuleId) ?? units[0];

  const clearFieldError = (
    field: HTMLTextAreaElement | HTMLInputElement | null,
  ) => {
    if (!field) return;
    field.removeAttribute("aria-invalid");
    const errorId = field.getAttribute("aria-describedby");
    if (errorId) {
      const error = document.getElementById(errorId);
      if (error) error.hidden = true;
    }
  };

  const showFieldError = (
    field: HTMLTextAreaElement | HTMLInputElement | null,
  ) => {
    if (!field) return;
    field.setAttribute("aria-invalid", "true");
    const errorId = field.getAttribute("aria-describedby");
    if (errorId) {
      const error = document.getElementById(errorId);
      if (error) error.hidden = false;
    }
  };

  const syncDraftFromFields = () => {
    state = {
      ...state,
      updatedAt: new Date().toISOString(),
      draft: {
        actualWork: fields.actualWork?.value ?? "",
        explanation: fields.explanation?.value ?? "",
        repoConnection: fields.repoConnection?.value ?? "",
        openQuestions: fields.openQuestions?.value ?? "",
      },
    };
  };

  const persist = async () => {
    syncDraftFromFields();
    try {
      await saveLearningState(state);
      setMessage("Saved in this browser", "ok");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save. Export a backup before leaving.",
        "error",
      );
    }
  };

  const scheduleSave = () => {
    setMessage("Saving…");
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => void persist(), 450);
  };

  const render = () => {
    const unit = currentUnit();
    const unitIndex = Math.max(
      0,
      units.findIndex((item) => item.id === unit?.id),
    );
    if (stateLabel) stateLabel.textContent = state.status;
    root
      .querySelectorAll<HTMLElement>("[data-current-number]")
      .forEach((item) => {
        item.textContent = unit?.number ?? "01";
      });
    const position = root.querySelector<HTMLElement>("[data-module-position]");
    if (position)
      position.textContent = `Module ${unitIndex + 1} of ${units.length}`;
    const title = root.querySelector<HTMLElement>("[data-current-title]");
    if (title) title.textContent = unit?.title ?? "";
    const exerciseTitle = root.querySelector<HTMLElement>(
      "[data-current-exercise-title]",
    );
    if (exerciseTitle) exerciseTitle.textContent = unit?.title ?? "";
    const summary = root.querySelector<HTMLElement>("[data-current-summary]");
    if (summary) summary.textContent = unit?.summary ?? "";
    const lesson = root.querySelector<HTMLElement>("[data-current-lesson]");
    if (lesson)
      lesson.innerHTML = (unit?.lesson ?? [])
        .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
        .join("");
    const exercise = root.querySelector<HTMLElement>("[data-current-exercise]");
    if (exercise) exercise.textContent = unit?.exercise ?? "";
    if (fields.actualWork)
      fields.actualWork.placeholder =
        unit?.workPlaceholder ?? "Record your work…";
    const explanationPrompt = root.querySelector<HTMLElement>(
      "[data-current-explanation]",
    );
    if (explanationPrompt)
      explanationPrompt.textContent = unit?.explanationPrompt ?? "";
    const gate = root.querySelector<HTMLElement>("[data-current-gate]");
    if (gate) gate.textContent = unit?.masteryGate ?? "";
    const source = root.querySelector<HTMLAnchorElement>(
      "[data-current-source]",
    );
    if (source && unit) source.href = unit.sourceHref;
    const sourceLabel = root.querySelector<HTMLElement>(
      "[data-current-source-label]",
    );
    if (sourceLabel) sourceLabel.textContent = unit?.sourceLabel ?? "";
    root
      .querySelectorAll<HTMLElement>("[data-module-one-only]")
      .forEach((item) => {
        item.hidden = unitIndex !== 0;
      });
    root
      .querySelectorAll<HTMLButtonElement>("[data-select-module]")
      .forEach((button) => {
        const active = button.dataset.selectModule === unit?.id;
        button.disabled = active;
        button.setAttribute("aria-current", active ? "step" : "false");
        button.textContent = active
          ? "Current session"
          : "Make this the current session";
      });
    const continuePanel = root.querySelector<HTMLElement>(
      "[data-continue-panel]",
    );
    const continueButton = root.querySelector<HTMLButtonElement>(
      "[data-continue-module]",
    );
    const next = units[unitIndex + 1];
    if (continuePanel && continueButton) {
      continuePanel.hidden = state.status === "reading" || !next;
      continueButton.dataset.continueModule = next?.id ?? "";
      continueButton.textContent = next
        ? `Continue to Module ${next.number}: ${next.title}`
        : "Course complete";
    }
    const due = dueRecalls(state);
    if (recallRegion) {
      const pending = state.checkpoints.flatMap((checkpoint) =>
        checkpoint.recalls
          .filter((recall) => recall.result === "pending")
          .map((recall) => ({ checkpoint, recall })),
      );
      if (pending.length === 0) {
        recallRegion.innerHTML =
          '<p class="empty-copy">Complete the immediate check to schedule recall at +2 and +7 days.</p>';
      } else {
        recallRegion.innerHTML = pending
          .map(({ checkpoint, recall }) => {
            const isDue = due.some(
              (item) =>
                item.checkpoint.id === checkpoint.id &&
                item.recall.id === recall.id,
            );
            return `<article class="recall-item" data-checkpoint="${escapeHtml(checkpoint.id)}" data-recall="${recall.id}">
            <div><span class="state-chip ${isDue ? "due" : "scheduled"}">${isDue ? "due now" : `due ${escapeHtml(recall.dueDate)}`}</span></div>
            <h3>${recall.id === "plus-2" ? "+2 day recall" : "+7 day recall"}</h3>
            <p>${escapeHtml(recall.prompt)}</p>
            <label>Closed-book response<textarea data-recall-response rows="5" ${isDue ? "" : "disabled"}>${escapeHtml(recall.response)}</textarea></label>
            <div class="review-actions">
              <button type="button" class="btn btn-ghost" data-recall-result="needs-repair" ${isDue ? "" : "disabled"}>Needs repair</button>
              <button type="button" class="btn btn-primary" data-recall-result="pass" ${isDue ? "" : "disabled"}>I can explain it</button>
            </div>
          </article>`;
          })
          .join("");
      }
    }
    if (historyRegion) {
      historyRegion.innerHTML =
        state.checkpoints.length === 0
          ? '<p class="empty-copy">No checkpoints yet. Your first saved explanation will appear here.</p>'
          : state.checkpoints
              .map((checkpoint) => {
                const checkpointUnit = units.find(
                  (item) => item.id === checkpoint.moduleId,
                );
                return `<details class="history-item"><summary>${escapeHtml(checkpointUnit?.title ?? checkpoint.moduleId)} · ${new Date(checkpoint.createdAt).toLocaleDateString()} · ${escapeHtml(checkpoint.immediateResult)}</summary><div><strong>Actual work</strong><p>${escapeHtml(checkpoint.actualWork)}</p><strong>Explanation</strong><p>${escapeHtml(checkpoint.explanation)}</p><strong>Repo connection</strong><p>${escapeHtml(checkpoint.repoConnection || "Not recorded")}</p><strong>Open questions</strong><p>${escapeHtml(checkpoint.openQuestions || "None recorded")}</p></div></details>`;
              })
              .join("");
    }
  };

  const hydrateFields = () => {
    if (fields.actualWork) fields.actualWork.value = state.draft.actualWork;
    if (fields.explanation) fields.explanation.value = state.draft.explanation;
    if (fields.repoConnection)
      fields.repoConnection.value = state.draft.repoConnection;
    if (fields.openQuestions)
      fields.openQuestions.value = state.draft.openQuestions;
  };

  for (const field of Object.values(fields))
    field?.addEventListener("input", () => {
      clearFieldError(field);
      scheduleSave();
    });

  root
    .querySelectorAll<HTMLButtonElement>("[data-immediate-result]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        syncDraftFromFields();
        const actualWorkMissing = !state.draft.actualWork.trim();
        const explanationMissing = !state.draft.explanation.trim();
        if (actualWorkMissing || explanationMissing) {
          if (actualWorkMissing) showFieldError(fields.actualWork);
          if (explanationMissing) showFieldError(fields.explanation);
          setMessage(
            "Add your calculation and explanation before recording the check.",
            "error",
          );
          (actualWorkMissing ? fields.actualWork : fields.explanation)?.focus();
          return;
        }
        const result =
          button.dataset.immediateResult === "pass" ? "pass" : "needs-repair";
        state = applyCheckpoint(state, createCheckpoint(state, result));
        await persist();
        render();
      });
    });

  const activateModule = async (moduleId: string) => {
    if (!units.some((unit) => unit.id === moduleId)) return;
    syncDraftFromFields();
    const latest = state.checkpoints.find(
      (checkpoint) => checkpoint.moduleId === state.currentModuleId,
    );
    const hasDraft = Object.values(state.draft).some((value) => value.trim());
    const hasUncheckpointedWork =
      hasDraft &&
      (!latest ||
        latest.actualWork !== state.draft.actualWork.trim() ||
        latest.explanation !== state.draft.explanation.trim() ||
        latest.repoConnection !== state.draft.repoConnection.trim() ||
        latest.openQuestions !== state.draft.openQuestions.trim());
    if (hasUncheckpointedWork) {
      setMessage(
        "Record this module's checkpoint before switching, or clear the draft fields.",
        "error",
      );
      fields.actualWork?.focus();
      return;
    }
    state = selectLearningModule(state, moduleId);
    hydrateFields();
    await persist();
    render();
    root.querySelector("#read")?.scrollIntoView({ behavior: "smooth" });
  };

  root.addEventListener("click", (event) => {
    const selectButton = (
      event.target as HTMLElement
    ).closest<HTMLButtonElement>("[data-select-module]");
    const continueButton = (
      event.target as HTMLElement
    ).closest<HTMLButtonElement>("[data-continue-module]");
    const moduleId =
      selectButton?.dataset.selectModule ??
      continueButton?.dataset.continueModule;
    if (moduleId) void activateModule(moduleId);
  });

  recallRegion?.addEventListener("click", async (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(
      "[data-recall-result]",
    );
    if (!button) return;
    const item = button.closest<HTMLElement>("[data-checkpoint][data-recall]");
    const response =
      item
        ?.querySelector<HTMLTextAreaElement>("[data-recall-response]")
        ?.value.trim() ?? "";
    if (!item || !response) {
      setMessage(
        "Write your closed-book response before recording the recall result.",
        "error",
      );
      item
        ?.querySelector<HTMLTextAreaElement>("[data-recall-response]")
        ?.focus();
      return;
    }
    const result =
      button.dataset.recallResult === "pass" ? "pass" : "needs-repair";
    state = completeRecall(
      state,
      item.dataset.checkpoint ?? "",
      item.dataset.recall as RecallCheck["id"],
      response,
      result,
    );
    await persist();
    render();
  });

  root
    .querySelector<HTMLButtonElement>("[data-export]")
    ?.addEventListener("click", () => {
      syncDraftFromFields();
      const blob = new Blob([JSON.stringify(makeBackup(state), null, 2)], {
        type: "application/json",
      });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `posttrainllm-learning-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      setMessage("Backup downloaded", "ok");
    });

  importInput?.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    if (!file) return;
    try {
      pendingImport = parseBackup(await file.text());
      const preview = root.querySelector<HTMLElement>("[data-import-preview]");
      if (preview) {
        preview.hidden = false;
        preview.querySelector<HTMLElement>(
          "[data-import-summary]",
        )!.textContent =
          `${pendingImport.state.checkpoints.length} checkpoint(s), updated ${new Date(pendingImport.state.updatedAt).toLocaleString()}.`;
      }
      setMessage("Backup validated. Choose merge or replace.", "ok");
    } catch (error) {
      pendingImport = null;
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not validate this backup.",
        "error",
      );
    } finally {
      importInput.value = "";
    }
  });

  root
    .querySelectorAll<HTMLButtonElement>("[data-import-mode]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        if (!pendingImport) return;
        const previous = makeBackup(state);
        const previousBlob = new Blob([JSON.stringify(previous, null, 2)], {
          type: "application/json",
        });
        const previousLink = document.createElement("a");
        previousLink.href = URL.createObjectURL(previousBlob);
        previousLink.download = `posttrainllm-learning-before-import-${new Date().toISOString().slice(0, 10)}.json`;
        previousLink.click();
        URL.revokeObjectURL(previousLink.href);
        state =
          button.dataset.importMode === "merge"
            ? mergeLearningState(state, pendingImport.state)
            : pendingImport.state;
        pendingImport = null;
        await persist();
        hydrateFields();
        render();
        const preview = root.querySelector<HTMLElement>(
          "[data-import-preview]",
        );
        if (preview) preview.hidden = true;
      });
    });

  void loadLearningState()
    .then((loaded) => {
      state = loaded;
      hydrateFields();
      render();
      setMessage("Saved in this browser", "ok");
    })
    .catch((error) => {
      render();
      setMessage(
        error instanceof Error
          ? error.message
          : "Browser storage is unavailable. Export before leaving.",
        "error",
      );
    });
}
