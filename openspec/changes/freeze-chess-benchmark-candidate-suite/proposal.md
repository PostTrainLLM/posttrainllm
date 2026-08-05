## Why

The 20-position Character Chess development gate found a real capability
gradient, but its labels are single Stockfish depth-12 choices and the sample is
too small for a frozen benchmark. Language-model agreement can identify
suspicious or ambiguous cases, but it cannot establish chess truth. The next
step is therefore a larger candidate pool whose engine labels are stable at
deeper search, with independent Claude/GPT screens recorded as secondary
evidence.

The runtime policy also needs a stronger legality contract. Prompting a model to
choose from `LEGAL` is not a guarantee. The action boundary must constrain or
mask the choice to the current legal set and disclose every intervention.

## What Changes

- Generate a deterministic 100-position candidate pool, separate from the
  original 20-position development gate.
- Re-label every candidate with Stockfish 18 at deeper search and retain only
  positions whose top move is stable and materially ahead of alternatives.
- Add a deterministic 40-position multi-model verification slice.
- Run Claude, free Devin GLM-5.2, and available lower GPT/Codex models on the identical slice with
  no tools, search, engine, code, or conversational state.
- Record strict/raw legality separately from constrained executed legality.
- Add a legal-action selector that accepts only a member of the canonical legal
  UCI set; provider failure abstains or redirects and never executes an illegal
  move.
- Retain unavailable, failed, timed-out, and superseded model attempts.

## Capabilities

### New Capabilities

- `chess-frozen-suite-candidate`: deterministic candidate generation, deep
  engine-label stability, independent model review, constrained selection, and
  admission evidence for a future frozen suite.

### Modified Capabilities

- `chess-language-policy-benchmark`: model results distinguish raw legality,
  constraint intervention, executed legality, abstention, and redirection.

## Impact

- Adds evaluation-only Python scripts, configs, fixtures, tests, and result
  artifacts under existing chess surfaces.
- Uses the already installed evaluation-only Stockfish and `python-chess`.
- Makes bounded external model calls explicitly requested by the owner. Codex
  subscription calls have no direct API spend; Devin GLM-5.2 is free; Claude
  identity, usage, and any exposed cost are recorded per attempt.
- Does not train a specialist, publish a frozen benchmark, deploy, or alter a
  production runtime.
