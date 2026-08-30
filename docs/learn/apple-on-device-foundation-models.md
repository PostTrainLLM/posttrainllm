---
title: Apple on-device Foundation Models — what they are, and where they fit (and don't)
description: What Apple's FoundationModels framework + on-device model give you, the bridge we built to score it on our gates, the measured verdict (can't ground actions; 4096-token context can't hold a tool catalog; not faster), and the strategic decision — use it as a free floor for routing, never as a dependency.
---

# Apple on-device Foundation Models — where they fit (and don't)

Apple's **FoundationModels** framework (macOS/iOS 26+) exposes an on-device ~3B model
through `LanguageModelSession` with structured output (`@Generable`), guided generation
(`DynamicGenerationSchema`), and a `Tool` protocol — plus an adapter slot
(`SystemLanguageModel(adapter:)`). Anthropic's `ClaudeForFoundationModels` conforms
*Claude* to the same protocol, so an app routes on-device↔cloud through one API.

We measured it on our own gates to see if it belongs in Pace. Verdict: **a free, private,
battery-cheap floor for lightweight turns — not an agentic action model, and not a
dependency.**

## The bridge (reusable artifact)

[`scripts/fm_agent_bridge.swift`](../../scripts/fm_agent_bridge.swift) — a standalone
Swift HTTP server that puts the on-device model behind the **OpenAI chat-completions +
tools** API our harness already speaks. Tool-calling is done with guided generation: per
request it builds a `DynamicGenerationSchema` (`{tool_calls:[{name(enum), arguments_json}], message}`)
and reads `GeneratedContent.jsonString` back out. So Apple's model becomes "just another
backend" — `DS_URL=…/v1/chat/completions` and our existing
[`bfcl_multiturn_deepseek.py`](../../scripts/bfcl/bfcl_multiturn_deepseek.py) scores it unchanged.
(Distinct from [`fm_bridge.swift`](../../scripts/fm_bridge.swift), the stdin/stdout bridge
for the single-turn Pace *planner* gate.)

## The verdict (measured)

| gate | result | why |
|---|---|---|
| BFCL agentic breadth, **full catalog** (n=8 VehicleControl) | **25%** | schemas present but ~3–4.4k-token catalog nearly overflows context |
| BFCL agentic breadth, **compact catalog** (52 tasks) | **~0%** | fits context, but stripping param schemas → wrong args |
| Pace **planner** gate (action-grounding) | **13%** | can pick intents, can't ground actions — see [benchmark README](https://github.com/PostTrainLLM/posttrainllm/blob/main/benchmarks/mac-assistant-judgment/README.md) |
| Pace planner gate (OOS-refusal) | **~95%** | judgment-light classification is its strength |

Three findings worth keeping:

1. **It can't ground actions.** It picks the right *tool name* (enum-constrained) but fills
   *arguments* wrong. Probe example: gold `lockDoors(unlock=True, door=['driver','passenger','rear_left','rear_right'])`;
   it emitted `lockDoors(unlock=false, door="all")` — inverted the boolean, guessed a string
   for an enum-list. Some gold args are **unguessable without the schema**.
2. **The catch-22.** Full catalog has the schemas → overflows the **4096-token context**;
   compact catalog fits → no schemas → wrong args. Either way the on-device context can't
   host a real agentic tool catalog.
3. **Not faster.** ~3–4s/step, same ballpark as our 4B (mlx_lm) which has ~8× the context.
   The win it *does* have is **perf-per-watt** (ANE vs GPU) + zero-setup/RAM/cost, not speed.

## Getting "our quality on Apple's battery" — the two paths, and why we declined one

- **Adapter-tune Apple's model** (`SystemLanguageModel(adapter:)`, `.fmadapter`): cleanest
  battery+integration win, but **locks us to Apple's model/format/OS**. **Decision: ruled out**
  — we own the model (see [AGENTS.md](https://github.com/PostTrainLLM/posttrainllm/blob/main/AGENTS.md)).
- **Core ML–compile *our own* weights to the ANE**: keeps ownership (Core ML is a deploy
  target, not a model dependency), but the ANE fights autoregressive decode (dynamic KV
  shapes, layout/dtype pickiness, partition+fallback). Possible later as a pure battery
  optimization; not a capability bet. Repo already has the toolchain (`ToCoreML.swift`,
  `CoreMLServe.swift`, `AneValidate.swift`).

## Where it fits

The free **floor tier** in a routing setup: on-device for lightweight, private, offline,
battery-sensitive turns (classification, refusal, short answers) → escalate to our distilled
4B for grounded agentic work → Claude for frontier. Apple commoditizes the *plumbing*
(on-device LLM + tools + structured output as an OS API); our differentiation stays the
**model + the eval gate**, not the serving layer.

## Related
- [Mac mastery map §3 (serving) + §7 (agents)](./mac-mastery-map.md)
- [mac-assistant-judgment benchmark](https://github.com/PostTrainLLM/posttrainllm/blob/main/benchmarks/mac-assistant-judgment/README.md) — full planner-gate table
- [Step-back inventory + ROI](../sessions/06-17-stepback-inventory-roi)
