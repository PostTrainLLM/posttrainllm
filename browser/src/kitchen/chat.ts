/** Opt-in chat controller. Real inference lives in a terminable worker.
 * Guide: docs/learn/llm-kitchen.md.
 */
import { chatModel } from "./chat-models";
import { dinnerPrompt } from "./model";
type Message = { role: "user" | "assistant"; content: string };
const el = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const selectedModel = () => chatModel;
const load = el<HTMLButtonElement>("load-chat");
const unload = el<HTMLButtonElement>("unload-chat");
const send = el<HTMLButtonElement>("send-chat");
const stop = el<HTMLButtonElement>("stop-chat");
const prompt = el<HTMLTextAreaElement>("chat-prompt");
const status = el("chat-status");
const engine = el("chat-engine");
const progress = el<HTMLProgressElement>("chat-progress");
const log = el("chat-log");
let worker: Worker | null = null;
let state: "idle" | "loading" | "ready" | "generating" = "idle";
let history: Message[] = [];
let answer = "";
let output: HTMLElement | null = null;
let watchdog: ReturnType<typeof setTimeout> | null = null;
function update() {
  load.disabled = state !== "idle";
  load.textContent =
    state === "idle"
      ? `Load local model · ${selectedModel().download}`
      : state === "loading"
        ? "Loading model…"
        : "Model loaded";
  el("chat-model-name").textContent = selectedModel().name;
  el<HTMLButtonElement>("try-dinner").disabled = state !== "ready";
  const stage = el("chat");
  const wasActive = stage.classList.contains("chat-active");
  const active = state === "ready" || state === "generating";
  stage.classList.toggle("chat-active", active);
  const context = stage.querySelector<HTMLDetailsElement>(".chat-context");
  if (context && window.matchMedia("(max-width: 600px)").matches) {
    if (active && !wasActive) context.open = false;
    else if (!active && wasActive) context.open = true;
  }
  el("chat-form").hidden = !active;
  unload.textContent = state === "loading" ? "Cancel download" : "Unload model";
  unload.disabled = state === "idle";
  send.disabled = state !== "ready";
  prompt.disabled = state !== "ready";
  stop.disabled = state !== "generating" && state !== "loading";
  el<HTMLButtonElement>("clear-chat").disabled = state === "generating";
  engine.textContent = {
    idle: "Not loaded",
    loading: "Downloading / initializing",
    ready: "Local · WASM",
    generating: "Generating locally",
  }[state];
}
function terminate(message: string) {
  worker?.terminate();
  worker = null;
  if (watchdog) clearTimeout(watchdog);
  watchdog = null;
  if (state === "generating" && output) {
    output.textContent = `${answer || "No text generated."}\n[Stopped; this partial reply is excluded from context.]`;
    if (history.at(-1)?.role === "user") history.pop();
  }
  state = "idle";
  progress.hidden = true;
  status.textContent = message;
  update();
}
function append(role: Message["role"], content: string) {
  log.querySelector(".chat-empty")?.remove();
  const message = document.createElement("p");
  message.className = "chat-message";
  message.dataset.role = role;
  const label = document.createElement("strong");
  label.textContent =
    role === "user" ? "You" : `${selectedModel().name} · live model`;
  const body = document.createElement("span");
  body.textContent = content;
  message.append(label, body);
  log.append(message);
  // Retain a bounded visible transcript too.
  while (log.children.length > 12) log.firstElementChild?.remove();
  return body;
}
load.addEventListener("click", () => {
  if (state !== "idle") return;
  state = "loading";
  update();
  status.textContent =
    "Fetching runtime and pretrained weights. Cancel at any time.";
  progress.hidden = false;
  progress.removeAttribute("value");
  let activeWorker: Worker;
  try {
    activeWorker = new Worker(new URL("./chat.worker.ts", import.meta.url), {
      type: "module",
    });
  } catch {
    terminate(
      "This browser blocked the model worker. Allow local workers or try a current browser, then load again.",
    );
    return;
  }
  worker = activeWorker;
  activeWorker.onerror = () =>
    terminate(
      "The browser could not start local inference. Check your connection and retry loading.",
    );
  activeWorker.onmessage = ({ data }) => {
    if (worker !== activeWorker) return;
    if (data.type === "progress") {
      const p = data.progress;
      if (typeof p.progress === "number") {
        progress.max = 100;
        progress.value = p.progress;
      } else progress.removeAttribute("value");
      const filename =
        typeof p.file === "string" ? p.file.split("/").pop() : "model files";
      status.textContent =
        typeof p.loaded === "number"
          ? `Downloading ${filename}: ${(p.loaded / 1e6).toFixed(1)} MB${typeof p.total === "number" ? ` of ${(p.total / 1e6).toFixed(1)} MB` : ""}.`
          : `Loading ${filename}…`;
    } else if (data.type === "ready") {
      state = "ready";
      progress.hidden = true;
      status.textContent =
        "Model ready. Send a prompt to see actual inference. Weights stay fixed.";
      update();
      prompt.focus();
    } else if (data.type === "token" && typeof data.chunk === "string") {
      answer += data.chunk;
      if (output) output.textContent = answer;
      log.scrollTop = log.scrollHeight;
      status.textContent = `Generating · ${answer.length} characters received. Stop ends computation.`;
    } else if (data.type === "done") {
      if (watchdog) clearTimeout(watchdog);
      watchdog = null;
      if (answer.trim())
        history.push({ role: "assistant", content: answer.slice(0, 1200) });
      else {
        if (output)
          output.textContent =
            "The model ended without a reply. Try a simpler prompt.";
        history.pop();
      }
      history = history.slice(-4);
      state = "ready";
      status.textContent =
        "Reply complete. Fixed pretrained weights; no training took place.";
      update();
      prompt.focus();
    } else if (data.type === "error")
      terminate(
        "Local inference failed. Stop released the worker. Check your connection, then reload to try again.",
      );
  };
  activeWorker.postMessage({ type: "load" });
});
el<HTMLFormElement>("chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const content = prompt.value.trim().slice(0, 800);
  if (!content || state !== "ready" || !worker) return;
  history = history.slice(-2);
  history.push({ role: "user", content });
  append("user", content);
  answer = "";
  output = append("assistant", "Preparing a reply…");
  prompt.value = "";
  state = "generating";
  update();
  status.textContent = "Computing the next token locally…";
  watchdog = setTimeout(
    () =>
      terminate(
        "Generation stopped at the 30-second limit. Reload to try a shorter prompt.",
      ),
    30000,
  );
  worker.postMessage({ type: "generate", messages: history });
});
stop.addEventListener("click", () =>
  terminate("Stopped. Worker terminated; reload the cached model to continue."),
);
unload.addEventListener("click", () =>
  terminate(
    "Model unloaded. Cached files may remain in your browser; no computation is running.",
  ),
);
el("clear-chat").addEventListener("click", () => {
  history = [];
  log.replaceChildren();
  prompt.value = "";
  status.textContent = "Conversation cleared. Start a new order.";
});
window.addEventListener("kitchen-leave-chat", () =>
  terminate("Model unloaded when you left the table. Reload to resume."),
);
window.addEventListener("pagehide", () => terminate("Model unloaded."));
update();

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    el<HTMLFormElement>("chat-form").requestSubmit();
  }
});
el("try-dinner").addEventListener("click", () => {
  prompt.value = dinnerPrompt;
  prompt.focus();
});
