# How to Cook an LLM — media package

Prepared 2026-10-02 as production-ready copy for the existing lesson. This is an unscheduled draft package; it makes no audience-size, performance, revenue, or model-quality claims.

## Main video: “A tiny language model, from garden to checkpoint”

**Target runtime:** about 6 minutes at a measured, explanatory pace. The timing below is an edit guide; record the full read and trim pauses, not caveats. Keep the lesson itself legible on screen. Use a real browser capture of the current article for product footage. Add simple labels or a hand-drawn garden-to-table map in the edit. Do not create synthetic browser screens, fake generated outputs, or staged SFT/preference training footage.

| Time | Voiceover (read as written) | Picture / edit |
| --- | --- | --- |
| 0:00–0:35 | “What does it mean to cook a language model? Here’s a small, inspectable version: choose some text, prepare it, train a tiny model, and see what its weights can do. This lesson follows one path from garden to table. The kitchen is a metaphor for the work; the controls underneath it are real. We’ll also mark the parts that are examples, because seeing a convincing answer on screen is not the same as measuring a model.” | Start on the current article’s welcome scene. Slow move across the garden illustration and six-stop map. On-screen label: “A learning lab, not a quality benchmark.” |
| 0:35–1:20 | “First, choose ingredients. In model training, those ingredients are examples. This lesson gives us a recipe note, a duplicate, a broken sample, a conversation, a little code sample, a cheese recipe, and even a weather forecast. They’re teaching fixtures, not a scraped dataset. I’ll select a few and ask: do these examples belong in the batch for the behavior I care about? That question matters. A cleaner file can still contain the wrong lesson.” | In the real Harvest scene, select the rice-and-beans sample and a second sample; show the basket count. Briefly reveal the cheese and forecast examples in the inspector to show why relevance is a human selection decision. Do not imply an audience or corpus is being collected. |
| 1:20–2:05 | “At the cutting board, we can inspect how this trainer represents text. This particular teaching model uses one token for each UTF-8 byte. The lesson shows the actual byte IDs for a short sentence. That is a real tokenizer, but it is deliberately simple: larger language models commonly group text into subword pieces. The knife helps us see the transformation. It is not a claim that every LLM chops words this way.” | Use the live Chop interaction and real token IDs for a short typed sentence. Keep the UI’s byte-token explanation visible. Add a small caption: “This lesson’s tokenizer: UTF‑8 bytes.” |
| 2:05–2:50 | “At the sink, preparation removes exact duplicates and a deliberately malformed sample from this small fixture. We can inspect the resulting text and token count. Notice what this filter does not do: it does not decide whether a clean example is useful, true, safe, or on-topic. We make that judgment by selecting the data. Preparing the batch changes the text we’ll train on; it does not change model weights.” | Capture the actual preparation action and status. Show the duplicate removal and broken sample exclusion only if the selected fixture produces those statuses. Include a close-up of “Model weights unchanged.” Never fabricate counts: select precisely the shown fixtures and retain their live count. |
| 2:50–4:15 | “Now the stove. This is the real training step in the journey. The prepared text is repeated into a tiny batch, and an existing WebAssembly trainer runs in an isolated worker. The model starts from random weights. When I press Cook, the screen reports real optimizer steps and training loss. The bounded lesson configuration uses byte tokens, one transformer layer, and at most 256 steps per click. This is a small next-token exercise, not a useful assistant arriving out of the oven. Repeating a tiny batch can demonstrate learning the batch; training loss alone does not tell us whether a model generalizes.” | Show the real Cook control, then a real run with step and loss status. Record your own session; do not composite or invent counters. If capture begins before training, state that cooking starts only when the button is pressed. Keep “tiny text generator” or equivalent limitation visible. |
| 4:15–5:05 | “The article also shows a base model, an SFT example, and a preference-trained example side by side. Those answers are authored illustrations. Selecting them changes the displayed example; it does not load three trained checkpoints or prove one is better. In the taste test, a choice collects one chosen-and-rejected pair. The separate simulation button is an explanation of a later optimization loop. It does not optimize weights or run an evaluation. Real supervised fine-tuning and preference optimization need their own training run and held-out checks.” | Show the checkpoint comparison with a persistent “Authored illustration — no model run” overlay. Show preference selection and the JSON pair only if useful, followed by the simulation label. Do not animate fake loss curves, model transitions, or evaluation pass badges. |
| 5:05–5:45 | “Back at the table, the lesson can generate from the same weights cooked at the stove. That is real inference from this tiny model, and generation does not update its weights. The output may be fragments or noise. We’re demonstrating the connection between training and inference, not recommending its dinner advice. You can download the actual checkpoint in the existing tinygpt format and open it in Web Lab.” | Use the real same-session cooker and table. Include a recording of a current model output only if captured live and label it “one run; not a quality result.” Never substitute a scripted sentence as model output. Show the actual download control. |
| 5:45–6:10 | “The point is to make each step visible: data selection, preparation, tokenization, training, inference, and a checkpoint you can carry forward. The runnable path is intentionally tiny. The post-training scenes teach the shape of later work, while staying honest about what has and hasn’t run. Open the lesson, follow the garden-to-table journey, and inspect the evidence for yourself.” | End on the article’s handoff/closing screen, then a clean title card with the canonical lesson URL. CTA: “Read and run the lesson: posttrainllm.com/articles/how-to-cook-an-llm”. |

### Recording notes and claim gates

- Record the live article directly. The root operator verified the canonical route returns HTTP 200 on 2026-10-02. That is route availability evidence, not a fresh interactive browser run.
- Existing retained runtime evidence is one actual WASM optimizer step, same-weight generation, and a 216,425-byte checkpoint export, followed by opening and continuing that checkpoint in Web Lab. Its generated text is noisy. This proves the integration path, not full-run quality.
- Current screenshots and audit captures in `artifacts/design/llm-kitchen/` document the UI journey. They can guide framing, but they are not substitute footage for a fresh recording. No recording was made for this package.
- SFT and preference response cards are authored illustrations. Preference collection creates one data pair; “Train on feedback (simulation)” performs no optimization or numeric simulation. Keep the illustration label visible in every clip using these controls.
- The article’s real model uses a deliberately bounded teaching setup. Do not claim it is an instruction-following assistant, a useful recipe generator, representative of larger LLM tokenizers, or evidence of generalization.

## Short 1 — “Your clean dataset can still be wrong” (about 40 seconds)

**Voiceover:** “This little batch has a duplicate, a broken sample, a cheese recipe, and a weather forecast. The lesson can remove exact duplicates and malformed text. But clean does not mean relevant. If I’m teaching a three-ingredient, dairy-free dinner assistant, I still have to decide whether each example belongs. Data cleaning fixes specific defects; it doesn’t choose the goal for me. In How to Cook an LLM, inspect the samples, prepare the batch, and see the real byte tokens before training.”

**Shots:** Real Harvest selection → inspector briefly showing cheese and forecast → real Prepare action/status → real token count. Use the counts produced by the recording; no overlays that invent filtering results.

**Caption:** Clean data can still teach the wrong thing. Choose examples for the behavior you want, then inspect what preparation actually changes. Try the interactive lesson: https://posttrainllm.com/articles/how-to-cook-an-llm

## Short 2 — “Watch a real optimizer step” (about 45 seconds)

**Voiceover:** “Here’s the real cooking step: a tiny byte-level model starts from random weights, learns from the batch we prepared, and reports optimizer steps and training loss. The controls use the existing WebAssembly trainer in an isolated worker. This is a wiring and learning demonstration, not proof that the model gives good answers. The batch is intentionally tiny, and loss on training text is not a generalization score. The useful part is that you can follow the data into training, then inspect the checkpoint it produced.”

**Shots:** Real prepared batch → click Cook → record live progress with counters legible → pause on the limitation text. Record an actual session; do not fabricate or speed-ramp counters to imply extra training.

**Caption:** Real, bounded WASM training from random weights. One-step evidence proves the path runs; it does not prove model quality. Explore the lesson: https://posttrainllm.com/articles/how-to-cook-an-llm

## Short 3 — “A vote is data, not training” (about 40 seconds)

**Voiceover:** “Choose the answer you prefer. The lesson turns that choice into one chosen-and-rejected example. That’s useful feedback data, but collecting it does not update a model. The next button is explicitly a simulation: it illustrates where an optimizer and held-out evaluation would fit, but it runs neither. The checkpoint cards beside it are authored examples too, not recordings from three trained models. That line between an illustration and a measured run is part of learning how post-training works.”

**Shots:** Real Taste test choice → inspect the one preference pair → point at the simulation label → show “authored illustration” checkpoint note. Keep those labels legible throughout.

**Caption:** A preference pair is a training input. It is not an optimizer run or proof of improvement. The lesson labels the boundary: https://posttrainllm.com/articles/how-to-cook-an-llm

## Companion description and CTA

**Title:** How to Cook an LLM: a tiny model from text to checkpoint

**Description:** Follow a small language-model lesson from sample selection to a real, bounded WebAssembly training run. Inspect byte-level tokenization, remove exact duplicates and malformed teaching samples, watch real optimizer steps, generate from the same cooked weights, and download the checkpoint for Web Lab.

The lesson’s SFT and preference response cards are authored illustrations. Choosing a preference collects one example; the separate simulation does not train or numerically evaluate a model. The one-step runtime proof establishes that the integration works, not that the tiny model is useful or generalizes.

**Open the interactive lesson:** https://posttrainllm.com/articles/how-to-cook-an-llm

## Sponsorship inventory offer

**One sponsor slot for this video package:** a clearly disclosed 15-second opening read, one static end-card logo, and one labeled link in the video description. The read can explain the sponsor’s relevant developer, local-computing, or technical-education offer in factual language supplied and approved by the sponsor. Editorial copy and the lesson remain independent; no sponsor claim about model results, audience reach, clicks, sales, or return is included or implied. Availability, placement, and any fee remain to be agreed directly before production. No audience metrics or rates are represented here.

## Source and proof pointers

- Lesson behavior and limits: [`docs/learn/llm-kitchen.md`](../../learn/llm-kitchen.md)
- Product purpose and truthful-claim commitments: [`PRODUCT.md`](../../../PRODUCT.md)
- Current lesson structure and labels: `browser/src/pages/articles/how-to-cook-an-llm.astro`
- Actual sample selection, byte encoding, authored checkpoint text, and preference pair: `browser/src/kitchen/model.ts`
- Real training and same-weight generation flow: `browser/src/kitchen/cooker.ts`
- Teaching configuration: `configs/llm-kitchen.json`
- Retained one-step WASM run and noisy completion: `artifacts/design/llm-kitchen/cook-real.json`
- Retained checkpoint reopen/continuation: `artifacts/design/llm-kitchen/export-reopen.json`
- Evidence index and limitation: `artifacts/design/llm-kitchen/README.md`
- Canonical article, live HTTP 200 verified by the root operator on 2026-10-02: https://posttrainllm.com/articles/how-to-cook-an-llm
