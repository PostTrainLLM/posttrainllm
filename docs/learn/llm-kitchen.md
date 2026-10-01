# How to Cook an LLM: lesson and integration notes

The [interactive article](https://posttrainllm.com/articles/how-to-cook-an-llm) is an illustrated field
guide for beginners. Its kitchen and model-development processes remain
visible together, with an explanation of the shared function at every station.

| Kitchen                   | Model development              | Shared function                                  | What changes?                                |
| ------------------------- | ------------------------------ | ------------------------------------------------ | -------------------------------------------- |
| Choose ingredients        | Select training data           | Choose material worth learning from              | Data                                         |
| Prepare and portion       | Clean, deduplicate, tokenize   | Make the material usable                         | Data                                         |
| Develop a base recipe     | Pre-train                      | Establish a foundation through repeated practice | Weights in a real run                        |
| Learn from worked recipes | Supervised fine-tuning         | Learn the desired result from demonstrations     | Trainable weights or adapters                |
| Taste, compare, revise    | Preference-based post-training | Use comparisons to guide improvement             | Feedback data first; trainable weights later |
| Serve a customer's order  | Inference                      | Use an already-developed recipe                  | Input, context, and output; weights fixed    |

Pre-training is already training, not data preparation. Both supervised
fine-tuning and preference optimization belong within post-training. Neither
is cosmetic. The metaphor does not imply that models understand food, follow
literal recipes, or that every model must pass through every stage.

## The six-stop journey

The owner-selected illustrated essay takes the learner from garden to cutting
board, sink, stove, and table. Kitchen and model explanations remain paired
within each scene. JavaScript presents one scene at a time with Back/Next and
browser-history navigation; the indicator shows the current scene, not mastery.
Every chapter is available without JavaScript.

1. **Harvest:** choose teaching samples. Selection carries forward to cleanup.
2. **Chop:** inspect real byte tokenization on a short editable sentence. This
   previews the representation; the actual full batch is cleaned and then
   encoded at the sink. Editing the sentence clears stale token pieces.
3. **Clean:** remove exact repeats and deliberately malformed samples from the
   selected harvest; inspect the resulting text and tokens, download, or offer
   the batch to the trainer.
4. **Cook:** explicitly train a tiny byte-level transformer from random weights
   on the prepared batch with the existing WASM trainer. Real loss and optimizer
   steps appear at the stove. Stop preserves the resulting checkpoint; Keep
   cooking continues that model on the same batch. Training is bounded to 256
   additional steps and 30 seconds per click.
5. **Refine and serve:** compare the existing authored checkpoints, collect
   preference data, separately illustrate optimization, then change an answer's
   heading as a presentation-only garnish. Refinement can change trainable
   weights; plating, garnish, and ordinary inference do not. Garnish is not
   presented as the technical mechanism of post-training.

6. **Talk:** complete a sentence with the same model trained at the stove.
   Download its actual weights in the existing `.tinygpt` format for Web Lab.
   This is a tiny text generator, not an instruction-following assistant.

No training starts from navigation or lesson restoration. Only Cook or Keep
cooking begins optimization. The selected batch is repeated to about 2 KB for
an intentional overfitting demonstration; loss is not a generalization score.

## Interaction details

### Prepare ingredients

The supplied samples are handwritten teaching material: an explanation, its
duplicate, malformed text, a conversation, and code. The learner chooses what
to keep. Preparation removes exact duplicates and rejects NUL/replacement
characters in this deliberately bounded fixture. This is not a general-purpose
data quality filter. Code and conversations are retained when selected.

The article imports `browser/src/tokenizer.ts`, the same UTF-8 byte tokenizer
as the trainer. It displays the prepared text, exact token count, and the first
64 token IDs. Every byte is a token; non-ASCII characters may occupy several
bytes. Larger LLMs often use subword tokenization. Preparing data does not
modify model weights. Changing the selection invalidates an old prepared batch.

### Compare checkpoints

One fixed dinner prompt appears at base, SFT, and preference checkpoints. All
responses are **authored illustrations, not recorded model outputs**. The
inspection panel shows the training objective, demonstration, or preference
pair. Switching checkpoints changes the displayed example only. Improvement
is neither measured nor guaranteed; a real run needs held-out evaluation and
regression checks.

### Collect feedback, then illustrate optimization

A taste-test choice creates a single chosen/rejected preference pair. Repeated
votes replace that pair rather than inflating a count. A separate **Train on
feedback (simulation)** action illustrates collecting a pair, optimizing,
obtaining candidate weights, and evaluating on held-out prompts. It performs
no optimization or numerical simulation. A poor choice explicitly illustrates
that preference data can teach the wrong thing. Re-voting clears the training
illustration; Reset clears the tray. The pair can be downloaded as JSONL.

DPO can directly optimize on preference pairs. In RLHF, preference judgments
can train a reward model used in a subsequent reinforcement-learning stage.
These mechanisms are different, even though they share the collection-versus-
optimization distinction.

## Browser trainer handoff

The article offers **Open this batch in the trainer** only after preparation.
It stores a versioned, source-tagged batch under
`posttrainllm.kitchen.batch.v1` in same-tab session storage, then navigates to
`/playground?kitchen=1`. Corpus text is not placed in the URL or sent to a
server by the handoff. Batches expire after an hour and are limited to 32 KB of
UTF-8 text. Invalid versions, sources, timestamps, and text are rejected.

The trainer waits for its normal initialization and existing-work restoration,
then offers an explicit corpus replacement with an incoming-text preview.
The learner can keep the existing corpus instead. An active training/model
operation blocks import. Import changes the corpus only; it does not reset,
start, or optimize a model, and does not erase saved checkpoints. The learner
must explicitly start a new run when ready. Storage failure has a text-download
and Upload fallback. The handoff is consumed on import or dismissal.

The existing trainer demonstrates tiny next-token training from scratch. It
does **not** reproduce the article's SFT/DPO scenes or promise a usable dinner
assistant from the tiny teaching batch. Real post-training belongs in the
[Mac fine-tuning guide](https://posttrainllm.com/fine-tune-llm-on-mac) and bounded native learning paths.

## Sources

- [Hugging Face: pre-training and fine-tuning](https://huggingface.co/learn/llm-course/chapter1/4)
- [InstructGPT: training with human feedback](https://arxiv.org/abs/2203.02155)
- [Direct Preference Optimization](https://arxiv.org/abs/2305.18290)

The article is a newly authorized learning surface tracked in
[Issue #182](https://github.com/PostTrainLLM/posttrainllm/issues/182), not a fresh
model experiment or reactivation of parked WebGPU work.


## Animated scenes and real cooking

The journey uses the existing WASM runtime in an isolated worker; it never saves
into the playground’s OPFS model slot. `configs/llm-kitchen.json` is the teaching configuration source of truth;
`kitchen/cook-model.ts` imports it and defines the canonical v1 `.tinygpt` export. `kitchen/cooker.ts`
connects the real prepared batch, actual loss/step messages, checkpoint, and
same-worker generation. It has no pretrained model, API, or added dependency.
Steam animates while the worker is training; reduced-motion disables animation.

Changing ingredients invalidates the prepared batch but preserves the old model
with an explicit previous-batch notice. Recooking explicitly replaces it; Keep
cooking is disabled until the original batch matches. Leaving the stove stops
an active run; leaving the table cancels generation and restores the last
checkpoint. Closing/reloading releases the worker. Weights stay in memory until
export; lesson restoration never recreates or trains weights automatically.

Generation requests 48 new byte tokens, with a 10-second bound. WASM generation
returns when complete rather than pretending to stream live tokens. Stop
terminates and restores the checkpoint in a new worker. Your prompts, selected
batch, and weights remain local. Lesson examples of SFT/preferences do not
modify the cooked model, and garnish changes presentation only.

## First-screen composition

The enhanced journey uses a compact two-column workspace: the animated kitchen
and corresponding model step sit beside the current interaction. Short headings,
44-pixel ingredient rows, and expandable full sample text keep the first decision
visible. Supporting explanations, provenance, preference data, and checkpoint
evidence remain available through disclosure controls. The tasting scene exposes
Examples, Taste test, and Serve activities individually. The complete article is
still rendered without JavaScript.

The welcome page exposes the six-stop map without duplicate navigation. Scene
Back/Next controls follow the workspace. Chat keeps the composer visible while
the growing transcript scrolls inside its own region. Expanded evidence can grow
beyond the first viewport. `browser/scripts/kitchen-viewport-audit.mjs` measures
primary interactions and navigation at desktop, laptop, tablet, and phone sizes;
the journey and chat audits verify that compact composition preserves behavior.


## Whole-journey usability contract

Next and Back visit Examples, Taste test, and Serve in sequence within the fifth
station, then reach live chat and an explicit final trainer handoff. Selecting an
activity updates browser history. Enhanced navigation avoids native fragment
scrolling into the reading notes; original reading anchors remain in the no-JS
article. Keyboard modifier clicks still work as ordinary links.

Known teaching choices are restored from bounded versioned same-tab session
storage with a one-hour TTL. Prepared text is regenerated from fixtures. No
weights, generated output, or chat prompts are persisted through this mechanism.
The final composer appears only after real cooking; use the batch’s first words
to try its completion. The model may produce fragments or noise even after a
short run. Download is the explicit way to keep its weights across page reloads.

`browser/scripts/kitchen-cook-audit.mjs` verifies the complete controlled UI
journey and lifecycle on desktop/phone. `LIVE_COOK=1` verifies one actual WASM
optimizer step, same-weight generation, and export. This bounded runtime check
is not evidence of full-run quality or useful dinner-assistant capability.

### Experience-first opening

The owner delegated the opening direction after reviewing three compositions.
The selected garden begins the harvest immediately with an empty basket and an
explicit goal: a three-ingredient, dairy-free dinner assistant. Neutral labels
and actual text replace category-only choices. The opening offers a dairy-free
recipe, a cheese recipe, and an unrelated forecast, all handwritten teaching
samples. The reader decides what helps the goal; no sample is preselected or
labelled “useful”. Picking a cheese recipe or forecast prompts a reflective
question, without blocking the learner from keeping it.

Basket names and counts mirror the canonical seven-sample lesson selection.
The full inspector also contains conversation, code, exact-repeat and malformed
examples. There is no second corpus. Changes invalidate prepared text and are
included in the bounded lesson session. Lesson schema/key v2 prevents older
preselected decisions from being restored under the changed sample set; trainer
model state and the version-1 batch handoff are unchanged.

The cutting-board action becomes available after picking at least one sample.
An empty basket keeps the action inactive; keyboard activation focuses the first
choice. The complete inspector remains reachable independently. Its enhanced
view has a bounded, keyboard-reachable scroll area so all seven sources remain
inspectable without displacing navigation. Without JavaScript, inert opening
controls stay hidden and the start link goes to the substantive harvest chapter.
No download, inference, or training begins on the opening screen.

Preparation removes exact duplicates and malformed text. It deliberately keeps
clean cheese/forecast examples if selected: relevance and dietary suitability
are selection judgments, not guaranteed by structural cleaning. The sink shows
that distinction alongside the real prepared corpus and tokens.

`kitchen-opening-audit.mjs` checks first-screen controls at desktop, tablet,
phone and narrow-phone sizes, source-card hit targets, keyboard selection,
canonical-state continuity, reload, empty-basket recovery, inspector-to-opening
synchronization, reduced motion and the reading fallback. Crop and basket motion
are finite and disabled by the user's reduced-motion preference.
