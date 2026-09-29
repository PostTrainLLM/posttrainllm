import {
  applyCheckpoint,
  activeRecallCheckpoints,
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
import type { InferenceSession, LessonSection } from "./inference-content";
import {
  learningRoutes,
  resolveSessionUrl,
  type LearningRouteId,
} from "./routes";

const root = document.querySelector<HTMLElement>("[data-learning-workspace]");

if (root) {
  const unitsElement = document.querySelector<HTMLScriptElement>(
    "#learning-units-data",
  );
  const units = unitsElement
    ? (JSON.parse(unitsElement.textContent ?? "[]") as Array<
        LearningUnit | InferenceSession
      >)
    : [];
  const fields = {
    diagnostic: root.querySelector<HTMLTextAreaElement>("#diagnostic"),
    prediction: root.querySelector<HTMLTextAreaElement>("#prediction"),
    actualWork: root.querySelector<HTMLTextAreaElement>("#actual-work"),
    explanation: root.querySelector<HTMLTextAreaElement>("#explanation"),
    repoConnection: root.querySelector<HTMLInputElement>("#repo-connection"),
    openQuestions: root.querySelector<HTMLTextAreaElement>("#open-questions"),
  };
  const foundationWorkedHtml =
    root.querySelector<HTMLElement>("[data-current-worked-example]")
      ?.innerHTML ?? "";
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

  const isInference = (
    unit: LearningUnit | InferenceSession,
  ): unit is InferenceSession =>
    "routeId" in unit && unit.routeId === "inference-systems-13w";

  const renderSections = (sections: LessonSection[]) =>
    sections
      .map(
        (section) =>
          `<section class="lesson-block"><h3>${escapeHtml(section.heading)}</h3>${(section.paragraphs ?? []).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}${section.bullets?.length ? `<ul>${section.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}${section.code ? `<pre><code>${escapeHtml(section.code)}</code></pre>` : ""}</section>`,
      )
      .join("");

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
        diagnostic: fields.diagnostic?.value ?? "",
        prediction: fields.prediction?.value ?? "",
        actualWork: fields.actualWork?.value ?? "",
        explanation: fields.explanation?.value ?? "",
        repoConnection: fields.repoConnection?.value ?? "",
        openQuestions: fields.openQuestions?.value ?? "",
      },
    };
    state.drafts[state.currentModuleId] = state.draft;
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
    const inference = unit && isInference(unit) ? unit : null;
    const sprint = inference !== null;
    const route = learningRoutes[state.currentRouteId];
    const unitIndex = Math.max(
      0,
      (route.orderedSessionIds as readonly string[]).indexOf(unit?.id ?? ""),
    );
    if (stateLabel) stateLabel.textContent = state.status;
    const diagnosticSection = root.querySelector<HTMLElement>(
      "[data-diagnostic-section]",
    );
    if (diagnosticSection)
      diagnosticSection.hidden = !inference?.diagnosticPrompt;
    const diagnosticPrompt = root.querySelector<HTMLElement>(
      "[data-current-diagnostic]",
    );
    if (diagnosticPrompt)
      diagnosticPrompt.textContent = inference?.diagnosticPrompt ?? "";
    const diagnosticRepair = root.querySelector<HTMLElement>(
      "[data-current-diagnostic-repair]",
    );
    if (diagnosticRepair)
      diagnosticRepair.textContent = inference?.diagnosticRepair ?? "";
    const repairDetails = root.querySelector<HTMLDetailsElement>(
      "[data-diagnostic-repair]",
    );
    if (repairDetails) repairDetails.open = false;
    const routeLabel = root.querySelector<HTMLElement>("[data-current-route]");
    if (routeLabel) routeLabel.textContent = route.title;
    const trackLabel = root.querySelector<HTMLElement>("[data-current-track]");
    if (trackLabel)
      trackLabel.textContent = sprint ? "Inference sprint" : "Foundations";
    root
      .querySelectorAll<HTMLElement>("[data-current-number]")
      .forEach((item) => {
        item.textContent = unit?.number ?? "01";
      });
    const position = root.querySelector<HTMLElement>("[data-module-position]");
    if (position)
      position.textContent = sprint
        ? `Week 1 · Day ${unitIndex + 1} of 7`
        : `Module ${unitIndex + 1} of ${route.orderedSessionIds.length}`;
    const meta = root.querySelector<HTMLElement>("[data-session-meta]");
    if (meta)
      meta.innerHTML = inference
        ? `<p><strong>${escapeHtml(inference.readiness)}</strong> · ${inference.minutes} minutes · ${escapeHtml(inference.hardware)}</p><p><strong>Goal:</strong> ${escapeHtml(inference.objective)}</p><p><strong>Before this:</strong> ${inference.prerequisites.map(escapeHtml).join("; ")}</p>`
        : "";
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
      lesson.innerHTML = inference
        ? renderSections(inference.sections)
        : (unit?.lesson ?? [])
            .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
            .join("");
    const worked = root.querySelector<HTMLElement>(
      "[data-current-worked-example]",
    );
    if (worked) {
      worked.hidden = !sprint && unitIndex !== 0;
      if (inference)
        worked.innerHTML = `<p class="mono-label">Worked example</p>${renderSections(inference.workedExample)}`;
      else worked.innerHTML = foundationWorkedHtml;
    }
    const predictionSection = root.querySelector<HTMLElement>(
      "[data-prediction-section]",
    );
    if (predictionSection) predictionSection.hidden = !sprint;
    const predictionPrompt = root.querySelector<HTMLElement>(
      "[data-current-prediction]",
    );
    if (predictionPrompt)
      predictionPrompt.textContent = inference?.predictionPrompt ?? "";
    const starter = root.querySelector<HTMLElement>("[data-current-starter]");
    if (starter) {
      starter.hidden = !inference?.starterCode;
      starter.innerHTML = inference?.starterCode
        ? `<p class="mono-label">Starter / exact command</p><pre><code>${escapeHtml(inference.starterCode)}</code></pre>`
        : "";
    }
    const answer = root.querySelector<HTMLElement>("[data-current-answer]");
    if (answer)
      answer.innerHTML = inference ? renderSections(inference.answerGuide) : "";
    const sprintAnswer = root.querySelector<HTMLDetailsElement>(
      "[data-inference-answer]",
    );
    if (sprintAnswer) {
      sprintAnswer.hidden = !sprint;
      sprintAnswer.open = false;
    }
    const foundationAnswer = root.querySelector<HTMLElement>(
      "[data-foundation-answer]",
    );
    if (foundationAnswer) foundationAnswer.hidden = sprint || unitIndex !== 0;
    const checks = root.querySelector<HTMLElement>("[data-current-checks]");
    if (checks) {
      checks.hidden = !sprint;
      checks.innerHTML = inference
        ? `<h3>Check your result</h3><ul>${inference.checks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><h3>Save as evidence</h3><ul>${inference.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
        : "";
    }
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
    const repair = root.querySelector<HTMLElement>("[data-repair-guidance]");
    if (repair) {
      const latest = state.checkpoints.find(
        (checkpoint) => checkpoint.moduleId === state.currentModuleId,
      );
      const failedRecall = latest?.recalls.find(
        (recall) => recall.result === "needs-repair",
      );
      const failed =
        latest?.immediateResult === "needs-repair" || Boolean(failedRecall);
      repair.hidden = !failed;
      repair.textContent = failed
        ? failedRecall
          ? `Repair this gap: ${failedRecall.prompt} Recheck: ${unit?.masteryGate ?? "the lesson check"} Your earlier response remains in checkpoint history. Answer the changed retry in the recall card below.`
          : `Repair this session's check: ${unit?.masteryGate ?? "review the exercise"} Keep your first attempt in history, change the example, and record a new immediate check.`
        : "";
    }
    const source = root.querySelector<HTMLAnchorElement>(
      "[data-current-source]",
    );
    if (source && unit) source.href = unit.sourceHref;
    const sourceLabel = root.querySelector<HTMLElement>(
      "[data-current-source-label]",
    );
    if (sourceLabel) sourceLabel.textContent = unit?.sourceLabel ?? "";
    root
      .querySelectorAll<HTMLElement>("[data-foundation-one-only]")
      .forEach((item) => {
        item.hidden = sprint || unitIndex !== 0;
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
    const next = units.find(
      (item) => item.id === route.orderedSessionIds[unitIndex + 1],
    );
    if (continuePanel && continueButton) {
      continuePanel.hidden = state.status === "reading" || !next;
      continueButton.dataset.continueModule = next?.id ?? "";
      continueButton.textContent = next
        ? sprint
          ? `Continue to Week 1, Day ${unitIndex + 2}`
          : `Continue to Module ${next.number}: ${next.title}`
        : "Course complete";
    }
    root
      .querySelectorAll<HTMLElement>("[data-session-content]")
      .forEach((item) => {
        if (!item.hasAttribute("data-prediction-section")) item.hidden = false;
      });
    root
      .querySelectorAll<HTMLAnchorElement>("[data-select-route]")
      .forEach((link) => {
        link.setAttribute(
          "aria-current",
          link.dataset.selectRoute === state.currentRouteId ? "page" : "false",
        );
      });
    const due = dueRecalls(state);
    if (recallRegion) {
      const openRecalls = activeRecallCheckpoints(state).flatMap((checkpoint) =>
        checkpoint.recalls
          .filter((recall) => recall.result !== "pass")
          .map((recall) => ({ checkpoint, recall })),
      );
      if (openRecalls.length === 0) {
        recallRegion.innerHTML =
          '<p class="empty-copy">Complete the immediate check to schedule recall at +2 and +7 days.</p>';
      } else {
        recallRegion.innerHTML = openRecalls
          .map(({ checkpoint, recall }) => {
            const needsRepair = recall.result === "needs-repair";
            const isDue =
              needsRepair ||
              due.some(
                (item) =>
                  item.checkpoint.id === checkpoint.id &&
                  item.recall.id === recall.id,
              );
            const checkpointUnit = units.find(
              (item) => item.id === checkpoint.moduleId,
            );
            const changedPrompt =
              checkpointUnit?.recallPrompts[recall.id === "plus-2" ? 1 : 0] ??
              checkpointUnit?.explanationPrompt ??
              recall.prompt;
            return `<article class="recall-item" data-checkpoint="${escapeHtml(checkpoint.id)}" data-recall="${recall.id}">
            <div><span class="state-chip ${isDue ? "due" : "scheduled"}">${needsRepair ? "repair retry" : isDue ? "due now" : `due ${escapeHtml(recall.dueDate)}`}</span></div>
            <h3>${recall.id === "plus-2" ? "+2 day recall" : "+7 day recall"}</h3>
            <p>${escapeHtml(needsRepair ? changedPrompt : recall.prompt)}</p>
            ${needsRepair ? `<p>Previous answer: ${escapeHtml(recall.response)}</p>` : ""}
            <label>Closed-book response<textarea data-recall-response rows="5" ${isDue ? "" : "disabled"}></textarea></label>
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
                const recallHistory = checkpoint.recalls.flatMap(
                  (recall) =>
                    recall.attempts ??
                    (recall.result !== "pending" && recall.completedAt
                      ? [
                          {
                            response: recall.response,
                            result: recall.result,
                            completedAt: recall.completedAt,
                          },
                        ]
                      : []),
                );
                return `<details class="history-item"><summary>${escapeHtml(checkpointUnit?.title ?? checkpoint.moduleId)} · ${new Date(checkpoint.createdAt).toLocaleDateString()} · ${escapeHtml(checkpoint.immediateResult)}</summary><div><strong>Initial diagnostic</strong><p>${escapeHtml(checkpoint.diagnostic || "Not recorded")}</p><strong>Initial prediction</strong><p>${escapeHtml(checkpoint.prediction || "Not recorded")}</p><strong>Actual work</strong><p>${escapeHtml(checkpoint.actualWork)}</p><strong>Explanation</strong><p>${escapeHtml(checkpoint.explanation)}</p><strong>Repo connection</strong><p>${escapeHtml(checkpoint.repoConnection || "Not recorded")}</p><strong>Open questions</strong><p>${escapeHtml(checkpoint.openQuestions || "None recorded")}</p><strong>Recall attempts</strong>${recallHistory.length ? `<ul>${recallHistory.map((attempt) => `<li>${escapeHtml(attempt.result)} · ${escapeHtml(attempt.response)}</li>`).join("")}</ul>` : "<p>None recorded</p>"}</div></details>`;
              })
              .join("");
    }
  };

  const hydrateFields = () => {
    if (fields.diagnostic) fields.diagnostic.value = state.draft.diagnostic;
    if (fields.prediction) fields.prediction.value = state.draft.prediction;
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
        const predictionMissing =
          state.currentRouteId === "inference-systems-13w" &&
          !state.draft.prediction.trim();
        const active = currentUnit();
        const diagnosticMissing = Boolean(
          active &&
          isInference(active) &&
          active.diagnosticPrompt &&
          !state.draft.diagnostic.trim(),
        );
        if (
          actualWorkMissing ||
          explanationMissing ||
          predictionMissing ||
          diagnosticMissing
        ) {
          if (actualWorkMissing) showFieldError(fields.actualWork);
          if (explanationMissing) showFieldError(fields.explanation);
          if (predictionMissing) showFieldError(fields.prediction);
          if (diagnosticMissing) showFieldError(fields.diagnostic);
          setMessage(
            "Save the initial check, prediction, actual work, and your own explanation before self-review.",
            "error",
          );
          (diagnosticMissing
            ? fields.diagnostic
            : predictionMissing
              ? fields.prediction
              : actualWorkMissing
                ? fields.actualWork
                : fields.explanation
          )?.focus();
          return;
        }
        const result =
          button.dataset.immediateResult === "pass" ? "pass" : "needs-repair";
        state = applyCheckpoint(state, createCheckpoint(state, result));
        await persist();
        render();
      });
    });

  const activateModule = async (moduleId: string, pushUrl = true) => {
    if (!units.some((unit) => unit.id === moduleId)) return;
    syncDraftFromFields();
    state = selectLearningModule(state, moduleId);
    hydrateFields();
    await persist();
    render();
    if (pushUrl)
      history.pushState(
        null,
        "",
        `/learn/session?route=${encodeURIComponent(state.currentRouteId)}&session=${encodeURIComponent(moduleId)}`,
      );
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

  root
    .querySelectorAll<HTMLAnchorElement>("[data-select-route]")
    .forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        const routeId = link.dataset.selectRoute as LearningRouteId;
        const route = learningRoutes[routeId];
        if (!route) return;
        const target =
          state.currentRouteId === routeId
            ? state.currentModuleId
            : ((route.orderedSessionIds as readonly string[]).find(
                (id) =>
                  state.drafts[id] ||
                  state.checkpoints.some(
                    (checkpoint) => checkpoint.moduleId === id,
                  ),
              ) ?? route.defaultSessionId);
        void activateModule(target);
      });
    });

  root
    .querySelector<HTMLDetailsElement>("[data-inference-answer]")
    ?.addEventListener("toggle", (event) => {
      const details = event.currentTarget as HTMLDetailsElement;
      if (!details.open) return;
      syncDraftFromFields();
      if (!state.draft.prediction.trim() || !state.draft.actualWork.trim()) {
        details.open = false;
        setMessage(
          "Record your prediction and attempt before opening the answer guide.",
          "error",
        );
        (!state.draft.prediction.trim()
          ? fields.prediction
          : fields.actualWork
        )?.focus();
      }
    });

  root
    .querySelector<HTMLDetailsElement>("[data-diagnostic-repair]")
    ?.addEventListener("toggle", (event) => {
      const details = event.currentTarget as HTMLDetailsElement;
      if (!details.open) return;
      syncDraftFromFields();
      if (!state.draft.diagnostic.trim()) {
        details.open = false;
        setMessage(
          "Record your first attempt before opening the worked repair.",
          "error",
        );
        fields.diagnostic?.focus();
      }
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
      const preview = root.querySelector<HTMLElement>("[data-import-preview]");
      if (preview) preview.hidden = true;
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
        hydrateFields();
        await persist();
        render();
        history.replaceState(
          null,
          "",
          `/learn/session?route=${encodeURIComponent(state.currentRouteId)}&session=${encodeURIComponent(state.currentModuleId)}`,
        );
        const preview = root.querySelector<HTMLElement>(
          "[data-import-preview]",
        );
        if (preview) preview.hidden = true;
      });
    });

  const applyRequestedUrl = async () => {
    const requested = resolveSessionUrl(window.location.search);
    const alert = root.querySelector<HTMLElement>("[data-route-alert]");
    if (alert) {
      alert.hidden = !requested.error;
      alert.textContent = requested.error ?? "";
    }
    if (requested.error || !requested.routeId) return;
    const route = learningRoutes[requested.routeId];
    const target =
      requested.sessionId ??
      (state.currentRouteId === requested.routeId
        ? state.currentModuleId
        : ((route.orderedSessionIds as readonly string[]).find(
            (id) =>
              state.drafts[id] ||
              state.checkpoints.some(
                (checkpoint) => checkpoint.moduleId === id,
              ),
          ) ?? route.defaultSessionId));
    if (target !== state.currentModuleId) {
      state = selectLearningModule(state, target);
      await saveLearningState(state);
    }
  };

  window.addEventListener("popstate", () => {
    syncDraftFromFields();
    void applyRequestedUrl().then(() => {
      hydrateFields();
      render();
    });
  });

  void loadLearningState()
    .then(async (loaded) => {
      state = loaded;
      await applyRequestedUrl();
      hydrateFields();
      render();
      setMessage("Saved in this browser", "ok");
    })
    .catch((error) => {
      // Reading remains available when IndexedDB is blocked. Honor an exact URL
      // in this temporary in-memory state without claiming it was saved.
      const requested = resolveSessionUrl(window.location.search);
      const alert = root.querySelector<HTMLElement>("[data-route-alert]");
      if (alert) {
        alert.hidden = !requested.error;
        alert.textContent = requested.error ?? "";
      }
      if (requested.routeId) {
        const route = learningRoutes[requested.routeId];
        state = selectLearningModule(
          state,
          requested.sessionId ?? route.defaultSessionId,
        );
      }
      hydrateFields();
      render();
      setMessage(
        error instanceof Error
          ? error.message
          : "Browser storage is unavailable. Export before leaving.",
        "error",
      );
    });
}
