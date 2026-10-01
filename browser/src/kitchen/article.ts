/** Article interactions. Real preparation and labelled post-training illustrations.
 * Guide: docs/learn/llm-kitchen.md.
 */
import {
  checkpoints,
  createBatch,
  HANDOFF_KEY,
  preferencePair,
  tasteResponses,
  prepareIngredients,
  type TasteChoice,
} from "./model";
import { encode } from "../tokenizer";
import { compactScenes } from "./layout";
import { initializeWelcome } from "./welcome";
import { LESSON_KEY, parseLesson, type Lesson } from "./session";

const byId = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const text = (id: string, value: string) => {
  byId(id).textContent = value;
};
let prepared: ReturnType<typeof prepareIngredients> | null = null;
let choice: TasteChoice | null = null;
let simulated = false;

function download(
  contents: string,
  filename: string,
  type = "text/plain;charset=utf-8",
) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function invalidateBatch() {
  const selected = document.querySelectorAll(
    "[data-ingredient]:checked",
  ).length;
  text(
    "harvest-status",
    `Your basket: ${selected} text sample(s) selected. Nothing has been cleaned or trained yet.`,
  );
  prepared = null;
  for (const id of ["open-trainer", "download-batch"])
    byId<HTMLButtonElement>(id).disabled = true;
  text("prepared-text", "Choose your text, then prepare a batch.");
  text("token-preview", "No batch prepared yet.");
  text(
    "prepare-status",
    "Selection changed. Prepare again to inspect or export this batch. Model weights unchanged.",
  );
  text("handoff-status", "");
}
document
  .querySelectorAll<HTMLInputElement>("[data-ingredient]")
  .forEach((input) => input.addEventListener("change", invalidateBatch));
const refreshWelcome = initializeWelcome();
byId("prepare-batch").addEventListener("click", () => {
  const ids = [
    ...document.querySelectorAll<HTMLInputElement>("[data-ingredient]:checked"),
  ].map((input) => input.value);
  prepared = prepareIngredients(ids);
  text(
    "prepared-text",
    prepared.text ||
      "No usable text remains. Keep a useful sample and try again.",
  );
  text(
    "token-preview",
    prepared.tokens.length
      ? `${prepared.tokens.length} UTF-8 byte tokens\nFirst ${Math.min(64, prepared.tokens.length)}: [${[...prepared.tokens.slice(0, 64)].join(", ")}]`
      : "No tokens: the batch is empty.",
  );
  text(
    "prepare-status",
    `${prepared.selected} selected → ${prepared.kept} kept · ${prepared.duplicates} exact duplicate(s) removed · ${prepared.rejected.length} broken sample(s) excluded. ${ids.includes("dairy") || ids.includes("weather") ? "Cleaning leaves your picked cheese recipe or forecast in the batch. Review whether each sample fits the dinner goal. " : ""}Model weights unchanged.`,
  );
  for (const id of ["open-trainer", "download-batch"])
    byId<HTMLButtonElement>(id).disabled = !prepared.text;
  text("handoff-status", "");
});
byId("download-batch").addEventListener("click", () => {
  if (prepared?.text) download(prepared.text, "llm-kitchen-batch.txt");
});
byId("open-trainer").addEventListener("click", () => {
  if (!prepared?.text) return;
  try {
    sessionStorage.setItem(
      HANDOFF_KEY,
      JSON.stringify(createBatch(prepared.text)),
    );
    window.location.assign("/playground?kitchen=1");
  } catch {
    text(
      "handoff-status",
      "Browser storage is unavailable. Download your batch, then use Upload in the browser trainer. No data was sent to a server.",
    );
  }
});

document
  .querySelectorAll<HTMLButtonElement>("[data-checkpoint]")
  .forEach((button) =>
    button.addEventListener("click", () => {
      const checkpoint = checkpoints.find(
        (item) => item.id === button.dataset.checkpoint,
      );
      if (!checkpoint) return;
      document
        .querySelectorAll("[data-checkpoint]")
        .forEach((other) =>
          other.setAttribute("aria-pressed", String(other === button)),
        );
      text("checkpoint-output", checkpoint.output);
      text("checkpoint-evidence", checkpoint.evidence);
      text("checkpoint-kitchen", checkpoint.kitchen);
      text("checkpoint-method", checkpoint.method);
      text(
        "checkpoint-change",
        `Real run: ${checkpoint.changed}. Here: illustrative output only.`,
      );
    }),
  );

function renderPreference() {
  byId<HTMLButtonElement>("simulate-feedback").disabled = choice === null;
  byId<HTMLButtonElement>("download-preference").disabled = choice === null;
  text(
    "preference-tray",
    choice
      ? JSON.stringify(preferencePair(choice), null, 2)
      : "Your tray is empty. Choose a response to collect a preference pair.",
  );
  text(
    "preference-status",
    choice
      ? `1 preference pair collected. ${simulated ? "Training illustration shown below; no preference training was performed." : "Model weights unchanged. Collecting a vote is not training."}`
      : "No preference collected. Model weights unchanged.",
  );
  byId("feedback-demo").hidden = !simulated;
  if (choice) {
    text(
      "feedback-example",
      choice === "b"
        ? "In this illustration, the later optimizer uses your chosen dairy-free response as a preferred example. Whether that improves a real model must be tested on held-out prompts."
        : "You preferred an answer with dairy. An optimizer can learn the wrong preference too. Feedback needs a clear criterion and review; it is not automatically a correctness label.",
    );
  }
}
document.querySelectorAll<HTMLButtonElement>("[data-taste]").forEach((button) =>
  button.addEventListener("click", () => {
    choice = button.dataset.taste as TasteChoice;
    simulated = false;
    document
      .querySelectorAll("[data-taste]")
      .forEach((other) =>
        other.setAttribute("aria-pressed", String(other === button)),
      );
    renderPreference();
  }),
);
byId("simulate-feedback").addEventListener("click", () => {
  if (!choice) return;
  simulated = true;
  renderPreference();
});
byId("reset-feedback").addEventListener("click", () => {
  choice = null;
  simulated = false;
  document
    .querySelectorAll("[data-taste]")
    .forEach((button) => button.setAttribute("aria-pressed", "false"));
  renderPreference();
});
byId("download-preference").addEventListener("click", () => {
  if (choice)
    download(
      `${JSON.stringify(preferencePair(choice))}\n`,
      "llm-kitchen-preference.jsonl",
      "application/x-ndjson",
    );
});

// The cutting board previews the real tokenizer. The finished batch is
// cleaned first and re-encoded by prepareIngredients at the sink.
byId("chop-preview").addEventListener("click", () => {
  const value = byId<HTMLInputElement>("chop-text").value;
  const tokens = encode(value);
  const pieces = byId("chopped-pieces");
  pieces.replaceChildren();
  for (const byte of tokens) {
    const piece = document.createElement("div");
    piece.className = "token-piece";
    piece.style.setProperty(
      "--piece-delay",
      `${pieces.children.length * 25}ms`,
    );
    piece.textContent =
      byte >= 33 && byte <= 126
        ? String.fromCharCode(byte)
        : byte === 32
          ? "␣"
          : "byte";
    const id = document.createElement("span");
    id.textContent = String(byte);
    piece.append(id);
    pieces.append(piece);
  }
  text(
    "chop-status",
    value
      ? `${tokens.length} UTF-8 byte tokens. Text representation changed; model weights unchanged. Clean the full harvest next, then encode that final batch.`
      : "The cutting board is empty. Add a sentence to inspect its tokens.",
  );
});
byId("chop-text").addEventListener("input", () => {
  byId("chopped-pieces").replaceChildren();
  text(
    "chop-status",
    "Text changed. Cut again to inspect the new tokens. Model weights unchanged.",
  );
});

// Cooking now belongs to the isolated real trainer, never lesson replay.
const cookStep = 0;
export const preparedBatch = () => prepared?.text ?? "";

let garnished = false;
byId("add-garnish").addEventListener("click", () => {
  garnished = !garnished;
  byId("add-garnish").setAttribute("aria-pressed", String(garnished));
  text(
    "served-output",
    `${garnished ? "Your dairy-free dinner\n\n" : ""}${tasteResponses.b}`,
  );
  text(
    "garnish-status",
    "Only the presentation changed. The underlying illustrative answer and model weights did not. Garnish is not post-training.",
  );
});

compactScenes();

// Scene navigation retains DOM state and has a complete no-JS reading fallback.
const stages = [
  ...document.querySelectorAll<HTMLElement>("[data-journey-stage]"),
];
const head = document.querySelector<HTMLElement>(".essay-head")!;
const sources = document.querySelector<HTMLElement>(".sources")!;
const names = [
  "Harvest",
  "Chop",
  "Clean",
  "Cook",
  "Refine & serve",
  "Your model",
];
const controls = byId("scene-controls");
controls.hidden = false;
document.querySelector("main")!.classList.add("scene-mode");
let current = -1;
function showScene(focus = true) {
  const hash = location.hash.slice(1);
  const index =
    hash === "taste" || hash === "serve"
      ? 4
      : stages.findIndex((stage) => stage.id === hash);
  if (["refine", "taste", "serve"].includes(hash))
    document
      .querySelector<HTMLButtonElement>(
        `[data-refine-panel="${hash === "refine" ? 0 : hash === "taste" ? 1 : 2}"]`,
      )
      ?.click();
  const previous = current;
  current = index;
  head.hidden = index !== -1;
  document.querySelector<HTMLElement>(".journey-nav")!.hidden = index < 0;
  controls.hidden = index < 0;
  sources.hidden = index !== 5;
  for (const [position, stage] of stages.entries()) {
    stage.hidden = position !== index;
    stage.classList.add("t-panel-slide");
    stage.dataset.open = "false";
    stage.classList.remove("scene-running");
  }
  if (index >= 0) {
    const stage = stages[index];
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        if (current !== index) return;
        stage.dataset.open = "true";
        stage.classList.add("scene-running");
      }),
    );
    if (focus) {
      const heading = stage.querySelector<HTMLElement>("h2")!;
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }
  if (previous === 5 && index !== 5)
    window.dispatchEvent(new Event("kitchen-leave-chat"));
  text(
    "journey-current-label",
    index < 0 ? "Your kitchen journey" : `0${index + 1} / ${names[index]}`,
  );
  text(
    "scene-count",
    index < 0
      ? "Six stops · your choices travel with you"
      : `${index + 1} of 6 · ${names[index]}`,
  );
  const back = byId<HTMLAnchorElement>("scene-back");
  const route = [
    "ingredients",
    "chopping",
    "cleaning",
    "base-recipe",
    "refine",
    "taste",
    "serve",
    "chat",
  ];
  const step = route.indexOf(hash);
  back.href = step <= 0 ? "#welcome" : `#${route[step - 1]}`;
  back.hidden = index < 0;
  const forward = byId<HTMLAnchorElement>("scene-forward");
  forward.href = `#${route[Math.min(step + 1, route.length - 1)]}`;
  const nextLabels = [
    "Cut your text →",
    "Wash the batch →",
    "Start cooking →",
    "Refine the recipe →",
    "Taste two versions →",
    "Plate & serve →",
    "Talk to the model →",
  ];
  forward.textContent = nextLabels[step] ?? "Begin →";
  if (index === 4)
    text(
      "scene-count",
      `5 of 6 · ${["Examples", "Taste test", "Serve"][hash === "refine" ? 0 : hash === "taste" ? 1 : 2]}`,
    );
  forward.hidden = false;
  if (index === 5) {
    forward.href = prepared?.text ? "/playground?kitchen=1" : "/playground";
    forward.textContent = prepared?.text
      ? "Explore the full trainer →"
      : "Open trainer →";
  }
  document
    .querySelectorAll<HTMLElement>("[data-journey-link]")
    .forEach((link, position) => {
      if (position === index) link.setAttribute("aria-current", "step");
      else link.removeAttribute("aria-current");
    });
  window.dispatchEvent(new Event("kitchen-scene-changed"));
  if (focus) window.scrollTo({ top: 0, behavior: "instant" });
}
byId("scene-forward").addEventListener("click", (event) => {
  if (current === 5 && prepared?.text) {
    event.preventDefault();
    byId("open-trainer").click();
  }
});
document.querySelector("main")!.addEventListener("click", (event) => {
  if (
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    event.altKey ||
    event.button !== 0
  )
    return;
  const link = (event.target as Element).closest<HTMLAnchorElement>("a[href]");
  const href = link?.getAttribute("href");
  if (
    !href ||
    ![
      "#welcome",
      "#ingredients",
      "#chopping",
      "#cleaning",
      "#base-recipe",
      "#refine",
      "#taste",
      "#serve",
      "#chat",
    ].includes(href)
  )
    return;
  event.preventDefault();
  if (location.hash !== href) history.pushState(null, "", href);
  showScene();
});
window.addEventListener("popstate", () => showScene());
window.addEventListener("kitchen-route", () => showScene());
window.addEventListener("hashchange", () => showScene());
showScene(false);

// Finite action-driven illustration; repeat clicks restart, hidden scenes stop.
function animateScene(element: Element | null) {
  const stage = element?.closest<HTMLElement>(".journey-stop");
  if (!stage) return;
  stage.classList.remove("scene-running");
  void stage.offsetWidth;
  stage.classList.add("scene-running");
}
for (const id of [
  "chop-preview",
  "prepare-batch",
  "cook-step",
  "simulate-feedback",
  "add-garnish",
])
  byId(id).addEventListener("click", (event) =>
    animateScene(event.currentTarget as Element),
  );
document
  .querySelectorAll("[data-ingredient]")
  .forEach((input) =>
    input.addEventListener("change", (event) =>
      animateScene(event.currentTarget as Element),
    ),
  );

// Restore only bounded teaching state; no download, inference or training starts.
try {
  const saved = parseLesson(sessionStorage.getItem(LESSON_KEY));
  if (saved) {
    document
      .querySelectorAll<HTMLInputElement>("[data-ingredient]")
      .forEach(
        (input) => (input.checked = saved.selected.includes(input.value)),
      );
    invalidateBatch();
    byId<HTMLInputElement>("chop-text").value = saved.chopText;
    if (saved.chopped) byId("chop-preview").click();
    if (saved.prepared) byId("prepare-batch").click();
    document
      .querySelector<HTMLButtonElement>(
        `[data-checkpoint="${saved.checkpoint}"]`,
      )
      ?.click();
    if (saved.choice)
      document
        .querySelector<HTMLButtonElement>(`[data-taste="${saved.choice}"]`)
        ?.click();
    if (saved.simulated) byId("simulate-feedback").click();
    if (saved.garnished) byId("add-garnish").click();

  }
} catch {
  /* Lesson still works without browser storage. */
}
refreshWelcome();
function saveLesson() {
  const state: Lesson = {
    version: 2,
    savedAt: Date.now(),
    selected: [
      ...document.querySelectorAll<HTMLInputElement>(
        "[data-ingredient]:checked",
      ),
    ].map((input) => input.value),
    chopText: byId<HTMLInputElement>("chop-text").value,
    chopped: byId("chopped-pieces").children.length > 0,
    prepared: !!prepared?.text,
    checkpoint: document.querySelector<HTMLElement>(
      '[data-checkpoint][aria-pressed="true"]',
    )!.dataset.checkpoint!,
    choice,
    simulated,
    garnished,
    cookStep,
  };
  try {
    sessionStorage.setItem(LESSON_KEY, JSON.stringify(state));
  } catch {
    /* No persistence; current scene state is retained. */
  }
}
for (const event of ["click", "change", "input"])
  document.querySelector("main")!.addEventListener(event, (event) => {
    const target = event.target as Element;
    if (target.closest("#chat")) return;
    saveLesson();
  });
window.addEventListener("pagehide", saveLesson);
