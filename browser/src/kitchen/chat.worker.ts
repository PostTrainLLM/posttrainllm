/** Isolated real pretrained inference. Termination stops download/compute.
 * Guide: docs/learn/llm-kitchen.md. No training or corpus handoff here.
 */
import { chatModel } from "./chat-models";
const scope = globalThis as unknown as {
  postMessage: (data: unknown) => void;
  onmessage: ((event: MessageEvent) => Promise<void>) | null;
};
const send = (type: string, data: Record<string, unknown> = {}) =>
  scope.postMessage({ type, ...data });
let generator: any = null;
let Streamer: any;
let generating = false;
scope.onmessage = async (event) => {
  try {
    if (event.data.type === "load") {
      if (generator) return send("ready");
      const runtime =
        "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.5";
      const { pipeline, TextStreamer, env } = await import(
        /* @vite-ignore */ runtime
      );
      Streamer = TextStreamer;
      env.allowLocalModels = false;
      env.backends.onnx.wasm.numThreads = 1;
      const model = chatModel;
      generator = await pipeline("text-generation", model.id, {
        revision: model.revision,
        device: "wasm",
        dtype: "int8",
        progress_callback: (progress: Record<string, unknown>) =>
          send("progress", { progress }),
      });
      send("ready");
    } else if (event.data.type === "generate" && generator && !generating) {
      const messages = event.data.messages;
      if (
        !Array.isArray(messages) ||
        messages.length > 4 ||
        messages.some(
          (m: any) =>
            !m ||
            !["user", "assistant"].includes(m.role) ||
            typeof m.content !== "string" ||
            m.content.length > 1200,
        )
      )
        throw new Error("Invalid conversation.");
      generating = true;
      await generator(
        [
          {
            role: "system",
            content:
              "You are a concise, helpful assistant. Answer directly in at most two sentences. Follow the user's ingredient count and dietary constraints. Here is one example of a three-ingredient dairy-free dinner: rice, beans, and tomatoes. Cook the rice, warm the beans, and combine with chopped tomatoes.",
          },
          ...messages,
        ],
        {
          max_new_tokens: 96,
          do_sample: false,
          streamer: new Streamer(generator.tokenizer, {
            skip_prompt: true,
            skip_special_tokens: true,
            callback_function: (chunk: string) => send("token", { chunk }),
          }),
        },
      );
      generating = false;
      send("done");
    }
  } catch (error) {
    generating = false;
    send("error", {
      message: error instanceof Error ? error.message : String(error),
    });
  }
};
export {};
