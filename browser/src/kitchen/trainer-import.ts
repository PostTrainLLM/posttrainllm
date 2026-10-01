/** Opt-in kitchen corpus handoff, after the trainer restores existing work.
 * Guide: docs/learn/llm-kitchen.md. Never starts or resets a model run.
 */
import { HANDOFF_KEY, parseBatch } from "./model";

export function offerKitchenBatch(
  corpus: HTMLTextAreaElement,
  isBusy: () => boolean,
  imported: () => void,
) {
  if (new URLSearchParams(window.location.search).get("kitchen") !== "1")
    return;
  let raw: string | null = null;
  try {
    raw = sessionStorage.getItem(HANDOFF_KEY);
  } catch {
    /* Show the download fallback below. */
  }
  const batch = parseBatch(raw);
  const panel = document.createElement("section");
  panel.className = "kitchen-import";
  panel.setAttribute("aria-label", "Kitchen lesson batch import");
  const heading = document.createElement("h3");
  heading.textContent = "Your kitchen batch";
  const status = document.createElement("p");
  status.setAttribute("role", "status");
  const back = document.createElement("a");
  back.href = "/articles/how-to-cook-an-llm#cleaning";
  back.textContent = "Continue the kitchen journey";
  panel.append(heading, status);
  if (batch) {
    status.textContent =
      "Importing replaces the text below, without starting training. Your saved model remains intact. This trainer learns next-token prediction; it does not run the article’s SFT or preference illustrations.";
    const preview = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent =
      "Inspect incoming text before replacing the current corpus";
    const content = document.createElement("pre");
    content.textContent = batch.text;
    preview.append(summary, content);
    panel.append(preview);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Replace corpus with kitchen batch";
    button.addEventListener("click", () => {
      if (isBusy()) {
        status.textContent =
          "Wait until the active training or model operation finishes before replacing the corpus. Nothing was imported.";
        return;
      }
      if (!parseBatch(JSON.stringify(batch))) {
        status.textContent =
          "This batch expired. Return to the article and prepare it again.";
        button.disabled = true;
        return;
      }
      corpus.value = batch.text;
      corpus.dispatchEvent(new Event("input", { bubbles: true }));
      imported();
      button.disabled = true;
      status.textContent =
        "Kitchen text imported. No training has started. Choose a small configuration and start explicitly when ready. A tiny corpus teaches the mechanism; it will not produce the illustrated dinner assistant.";
      try {
        sessionStorage.removeItem(HANDOFF_KEY);
      } catch {
        /* Import has already succeeded. */
      }
    });
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.textContent = "Keep current corpus";
    dismiss.addEventListener("click", () => {
      try {
        sessionStorage.removeItem(HANDOFF_KEY);
      } catch {
        /* Dismiss still works. */
      }
      panel.remove();
    });
    panel.append(button, dismiss);
  } else {
    status.textContent =
      "No valid kitchen batch is available in this tab. Return to the article to prepare one, or download its text and use Upload here. Your existing work is unchanged.";
  }
  panel.append(back);
  corpus.before(panel);
}
