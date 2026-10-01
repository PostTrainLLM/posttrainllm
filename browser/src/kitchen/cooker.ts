/** Cook and serve the SAME isolated trainer model; never overwrite Web Lab OPFS.
 * Guide: docs/learn/llm-kitchen.md.
 */
import { preparedBatch } from "./article";
import { cookingCorpus, kitchenConfig, kitchenModelFile } from "./cook-model";
import type { FromWorker, ToWorker } from "../types";
const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const button = (id: string) => el<HTMLButtonElement>(id);
let worker: Worker | null = null;
let phase: "empty" | "training" | "ready" | "generating" | "restoring" = "empty";
let checkpoint: ArrayBuffer | null = null;
let cookedBatch = "";
let corpus = "";
let canContinue = false;
let output: HTMLElement | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
let killTimer: ReturnType<typeof setTimeout> | undefined;
let points: { step: number; loss: number }[] = [];
function timersOff() { clearTimeout(timer); clearTimeout(killTimer); }
function update() {
  const busy = phase === "training" || phase === "generating" || phase === "restoring";
  button("cook-step").disabled = busy || !preparedBatch();
  button("cook-step").textContent = checkpoint ? "Cook a fresh model →" : "Cook my model →";
  button("reset-cook").disabled = phase !== "ready" || !canContinue || cookedBatch !== preparedBatch();
  button("stop-cook").disabled = phase !== "training";
  button("send-chat").disabled = phase !== "ready";
  button("try-dinner").disabled = phase !== "ready";
  el<HTMLTextAreaElement>("chat-prompt").disabled = phase !== "ready";
  button("stop-chat").disabled = phase !== "generating";
  button("download-cooked").disabled = !checkpoint || busy;
  button("clear-chat").disabled = phase === "generating";
  el("chat-engine").textContent = { empty: "Not cooked yet", training: "Cooking · WASM", ready: "Your weights · WASM", generating: "Predicting next bytes", restoring: "Restoring your weights" }[phase];
  el("cook-corpus").textContent = preparedBatch() || "No prepared batch yet.";
  el("base-recipe").classList.toggle("model-cooking", phase === "training");
  const activeBefore = el("chat").classList.contains("chat-active");
  el("chat").classList.toggle("chat-active", !!checkpoint);
  if (checkpoint && !activeBefore && window.matchMedia("(max-width: 600px)").matches) {
    const context = el("chat").querySelector<HTMLDetailsElement>(".chat-context");
    if (context) context.open = false;
  }
  el("chat-form").hidden = !checkpoint;
  if (checkpoint && cookedBatch !== preparedBatch()) {
    el("chat-status").textContent = "This model learned your previous batch. Return to the stove to cook the new ingredients.";
  }
}
function send(message: ToWorker) { worker?.postMessage(message); }
function failure(message: string) {
  timersOff(); worker?.terminate(); worker = null;
  phase = "empty"; checkpoint = null; canContinue = false;
  el("cook-status").textContent = message;
  el("chat-status").textContent = "No model ready. Return to the stove and try again.";
  update();
}
function createWorker() {
  worker?.terminate();
  const current = new Worker(new URL("../worker.ts", import.meta.url), { type: "module" });
  worker = current;
  current.onerror = () => failure("The trainer could not start. Your batch is intact; try cooking again.");
  current.onmessage = ({ data }: MessageEvent<FromWorker>) => {
    if (worker !== current) return;
    if (data.type === "progress") {
      const p = data.progress;
      points.push({ step: p.step, loss: p.trainLoss });
      el("cook-counter").textContent = `${p.step} / ${p.maxSteps}`;
      el("cook-loss").textContent = p.trainLoss.toFixed(3);
      el<HTMLProgressElement>("cook-progress").max = p.maxSteps;
      el<HTMLProgressElement>("cook-progress").value = p.step;
      const ymax = Math.max(6, ...points.map(p => p.loss));
      document.getElementById("cook-curve")!.setAttribute("points", points.map(p => `${p.step / data.progress.maxSteps * 320},${70 - p.loss / ymax * 64}`).join(" "));
      el("cook-status").textContent = p.step ? `Heat on · ${p.step} real optimizer steps · ${Math.round(p.tokensPerSecond).toLocaleString()} tokens/s. Weights are changing.` : "Fresh random weights. Predict → compare → update, using your batch.";
    } else if (data.type === "status" && phase === "training") {
      el("cook-status").textContent = data.message;
    } else if (data.type === "checkpoint") {
      checkpoint = data.state;
    } else if (data.type === "done") {
      timersOff();
      if (!checkpoint) { failure("Cooking ended without a checkpoint. Try again."); return; }
      phase = "ready"; canContinue = true;
      el("cook-status").textContent = `${data.reason === "stopped" ? "Heat off" : "Cooked"} · ${points.at(-1)?.step ?? 0} optimizer steps. Taste your model at the table, or keep cooking.`;
      el("chat-status").textContent = "Your cooked weights are ready. Start with words from your batch; this is a tiny text generator.";
      el("chat-log").replaceChildren();
      update();
    } else if (data.type === "restored") {
      timersOff(); phase = "ready"; canContinue = true;
      el("chat-status").textContent = "Generation stopped. Your trained weights are restored; try a shorter opening.";
      update();
    } else if (data.type === "sample_done" || data.type === "sample") {
      timersOff();
      if (output) output.textContent = data.text || "[No continuation produced.]";
      phase = "ready";
      el("chat-status").textContent = "Actual output from your cooked model. Its weights did not change during generation.";
      update();
      el("chat-log").scrollTop = el("chat-log").scrollHeight;
    } else if (data.type === "error") failure(`Cooking failed: ${data.message}. Your ingredients are still available.`);
  };
}
function train(continuing: boolean) {
  if (phase === "training" || phase === "generating" || phase === "restoring") return;
  if (continuing && (phase !== "ready" || !canContinue || cookedBatch !== preparedBatch())) return;
  if (!preparedBatch()) { el("cook-status").textContent = "Prepare your ingredients at the sink first."; return; }
  try {
    if (!continuing) {
      cookedBatch = preparedBatch(); corpus = cookingCorpus(cookedBatch);
      points = []; checkpoint = null; canContinue = false;
      createWorker();
    }
    phase = "training"; update();
    el("cook-status").textContent = "Heating the stove. Training stays in this browser.";
    send(continuing ? { type: "continue", extraSteps: kitchenConfig.maxSteps } : { type: "train", text: corpus, config: kitchenConfig });
    timer = setTimeout(stopTraining, 30000);
  } catch { failure("The trainer could not start. Try a current browser and cook again."); }
}
function stopTraining() {
  if (phase !== "training") return;
  clearTimeout(timer); clearTimeout(killTimer); button("stop-cook").disabled = true;
  send({ type: "stop" });
  el("cook-status").textContent = "Turning off the heat and saving the weights…";
  killTimer = setTimeout(() => failure("The trainer did not stop in time and was released. Cook again to start a new model."), 3000);
}
button("cook-step").addEventListener("click", () => train(false));
button("reset-cook").addEventListener("click", () => train(true));
button("stop-cook").addEventListener("click", stopTraining);
el<HTMLFormElement>("chat-form").addEventListener("submit", event => {
  event.preventDefault();
  const prompt = el<HTMLTextAreaElement>("chat-prompt").value.trim();
  if (!prompt || phase !== "ready") return;
  el("chat-log").querySelector(".chat-empty")?.remove();
  const row = document.createElement("p"); row.className = "chat-message"; row.dataset.role = "assistant";
  const label = document.createElement("strong"); label.textContent = `Your opening: ${prompt}`;
  output = document.createElement("span"); output.textContent = "Computing your model’s continuation…";
  row.append(label, output); el("chat-log").append(row);
  while (el("chat-log").children.length > 6) el("chat-log").firstElementChild?.remove();
  phase = "generating"; update();
  send({ type: "sample", prompt: prompt.slice(0, 128), tokens: 48, temperature: 0.7 });
  timer = setTimeout(stopGeneration, 10000);
});
function stopGeneration() {
  if (phase !== "generating" || !checkpoint) return;
  timersOff(); if (output) output.textContent = "[Generation stopped.]";
  const state = checkpoint.slice(0);
  try {
    createWorker(); phase = "restoring"; update();
    send({ type: "restore", state, config: kitchenConfig, corpus });
    timer = setTimeout(() => failure("Could not restore the cooked model. Your downloaded checkpoint can still be opened in Web Lab."), 10000);
  } catch { failure("Could not restore the cooked model. Return to the stove."); }
}
button("stop-chat").addEventListener("click", stopGeneration);
button("try-dinner").addEventListener("click", () => {
  el<HTMLTextAreaElement>("chat-prompt").value = cookedBatch.split(/\s+/).slice(0, 3).join(" ");
  el("chat-prompt").focus();
});
el("chat-prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); el<HTMLFormElement>("chat-form").requestSubmit(); }
});
button("clear-chat").addEventListener("click", () => el("chat-log").replaceChildren());
button("download-cooked").addEventListener("click", () => {
  if (!checkpoint) return;
  const url = URL.createObjectURL(kitchenModelFile(kitchenConfig, checkpoint, corpus));
  const link = document.createElement("a"); link.href = url; link.download = "my-kitchen-model.tinygpt"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener("pagehide", () => { timersOff(); worker?.terminate(); });
// Keep trained weights alive between scenes; cancel active work when leaving.
window.addEventListener("kitchen-scene-changed", () => {
  if (phase === "training" && location.hash !== "#base-recipe") stopTraining();
  if (phase === "generating" && location.hash !== "#chat") stopGeneration();
});
window.addEventListener("kitchen-leave-chat", stopGeneration);
document.querySelectorAll("[data-ingredient]").forEach(input => input.addEventListener("change", update));
button("prepare-batch").addEventListener("click", () => {
  update();
  if (phase !== "training") el("cook-status").textContent = preparedBatch() ? "Ingredients ready. Turn on the heat to train your own model." : "No usable batch. Return to the garden.";
});
update();
