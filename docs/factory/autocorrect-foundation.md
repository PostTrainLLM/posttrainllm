# Mac-local autocorrect foundation

Status: no-model foundation verified on 2026-07-25. No model was downloaded,
loaded, calibrated, trained, compiled, or benchmarked.

## Decision and boundary

The owner explicitly reprioritized finishing the OpenSpecs on 2026-07-25, so
the foundation tranche of `build-mac-local-autocorrect-specialist` moved ahead
of a model run. The boundary is deliberate:

- complete the correction contract, evaluator, provenance/split validation,
  keyboard simulator, tiny manifests, and comparator assessment;
- calibrate the frozen fixture with Codex while leaving every local model/GPU
  stage pending;
- do not claim that the 18-row smoke fixture is a production benchmark.

The machine-readable source of truth is
[`evals/autocorrect/`](../../evals/autocorrect/). The protocol accepts one
English UTF-8 prose span of at most 512 bytes and returns only the minimally
corrected span. URLs, numbers, backtick code, and fixture-declared names or rare
words are protected. Grammar rewriting, style changes, translation, next-word
prediction, and keyboard/UI integration are out of scope.

## Tiny source and eval

The committed source is original, owner-authorized for this tranche, and
licensed under the repository MIT license. Its revision is the SHA-256 of
`source-documents-v1.jsonl`; no retrieval or network step exists. Private
typing logs and external corpora with unverified revisions or terms are
excluded.

The frozen eval has:

| Slice | Rows | Purpose |
|---|---:|---|
| Reviewed original error examples | 12 | One unambiguous target per row across all seven keyboard-error families |
| Clean controls | 6 | Overcorrection and byte-preservation gate |
| Lexical holdout | `quokka`, `sesquipedalian`, `zyzzyva` | Present only in test sources |
| Protected content | names, numbers, URLs, code, rare words | Byte-exact preservation |

These are manually constructed and reviewed examples of ordinary typing
mistakes. They are sufficient to prove evaluator and data-path behavior, but
not to estimate real-world prevalence or support a headline model claim. Before
a final model evaluation, add a larger independently verified permissive or
consented natural source as a new fixture version; do not mutate v1 after
candidate outputs exist.

## Strict evaluator

`scripts/autocorrect_foundation.py evaluate` requires exactly one string
prediction per frozen ID and rejects missing, duplicate, extra, or expanded
records. It reports:

- micro error-reduction rate, including negative values without clamping;
- exact match and residual character error;
- byte-exact clean preservation;
- deterministic minimum-edit unnecessary-edit rate;
- protected-span preservation;
- every committed slice plus per-row distances.

Zero-error clean controls have a null error-reduction value instead of a
division-by-zero surrogate. A changed clean control still counts as an
unnecessary edit and protected-span failure.

## Source-first data path

Clean documents are assigned to `train`, `development`, or `test` before any
derivative exists. The validator enforces that the derivative inherits its
source split and rejects exact or NFKC/case/whitespace-normalized overlap across
splits. It also verifies source/license fields, source and dataset SHA-256
values, counts, lexical holdouts, edit-trace replay, and deterministic
reproduction.

Only two future-training manifests exist:

| Manifest | Rows | Serialized bytes | Splits | Purpose |
|---|---:|---:|---|---|
| `autocorrect-tiny-overfit-v1` | 8 | 3,321 | train only | One example per family plus a clean control; below the 10 KB gate |
| `autocorrect-pilot-v1` | 16 | 6,981 | 12 train / 4 development | Bounded pilot; no test document |

No training dataset was expanded beyond these manifests.

## Mac keyboard simulator and distribution

The simulator uses the committed US ANSI Mac layout and a SHA-256 counter
stream, avoiding runtime-global PRNG state. It supports adjacent-key
substitution, insertion, omission, transposition, repetition, space
insertion/removal, and shift/case errors. Every result carries source/noisy
offsets, source text, replacement text, family, and mode; clean controls have
an empty trace.

The 12 reviewed error events and the 256-row deterministic simulator sample
compare as follows:

| Family | Reviewed | Synthetic |
|---|---:|---:|
| substitution | 16.7% | 20.7% |
| insertion | 8.3% | 6.6% |
| omission | 8.3% | 9.8% |
| transposition | 33.3% | 32.4% |
| repetition | 8.3% | 7.0% |
| space | 16.7% | 16.0% |
| shift/case | 8.3% | 7.4% |

The total-variation distance is 0.0547 after setting only the training-side
family weights to the reviewed fixture counts. The natural fixture and its hash
did not change. These weights are a smoke prior, not an empirical claim; a
larger licensed natural sample must produce a new simulator config version.

## Apple autocorrect assessment

Read-only inspection of the locally installed macOS 27 AppKit SDK found:

- `NSSpellChecker.checkString` returns checking results;
- `NSSpellChecker.correctionForWordRange` proposes one correction for an
  explicit word range;
- `NSTextView.automaticSpellingCorrectionEnabled` participates in an
  interactive text-view lifecycle.

No inspected public API accepts the same complete prose span and returns the
final whole-span autocorrect output used during interactive typing. A custom
loop that applies word corrections would be a new protocol, and interactive
behavior may depend on language, user preferences, learned spellings, document
state, and typing order. Apple autocorrect is therefore frozen as an
**observational, non-equivalent baseline**. It must not appear in the direct v1
error-reduction or frontier-parity table. Exact SDK paths and hashes are in
`apple-autocorrect-assessment-v1.json`.

## Calibration and pending blockers

Task 2.5 is complete. Codex CLI 0.145.0 with `gpt-5.6-sol` received only the
committed fixture, matched all 18 rows exactly, preserved every clean/protected
span, and required no fixture repair or removal. Invocation provenance and
hashes are in `evals/autocorrect/frontier-calibration-v1.json`. This establishes
that the tiny smoke ruler is unambiguous; it does not make it representative.

Task 4.1 is also complete. The pinned three-candidate shortlist and exact
resource gate are in `autocorrect-model-shortlist.md`.

- Tasks 4.2-4.5 require immediate approval before the recorded downloads,
  dependency installation, model loads, or bounded bake-off.
- Tasks 5.1-5.7: require a selected base and explicit approval for any
  dependency, compilation, model load, GPU lock, overfit, or pilot training.
- Tasks 6.1-6.4: require real greedy/beam decoding and resource/energy
  measurements.
- Tasks 7.1-7.6: require calibrated comparators, trained candidates, complete
  performance evidence, and a real decision. No package or archive is valid
  before those exist.
