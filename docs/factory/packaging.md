# Factory Packaging

A shipped specialist needs a small, inspectable package. The package metadata is
committed; the large model or adapter artifact usually stays under
`~/.cache/posttrainllm/models/` or another local/cache path.

## Package Layout

```text
specialists/<specialist-id>/
  artifact-manifest.json
  model_card.md
  eval_report.json
  tinygpt.lock.json
  prompt.md
  report.md
```

Use `specialists/qwen3-4b-file-ops-distilled/` as the current pattern.

## Required Model Card Fields

- what the specialist is for
- what it must not be used for
- base model
- artifact path
- training method
- primary eval result
- regression/breadth result
- known limits
- routing requirements if any

## Required Lock Fields

- base model id and revision
- architecture
- precision
- artifact path
- tokenizer/template assumptions
- eval suite ids
- package date

The lifecycle manifest is the runtime authority for artifact kind, pinned base
and tokenizer, bounded production history, compatible runtimes, and legal next
actions. The lock remains package metadata and may repeat selected fields for
human inspection, but must not contradict the manifest. See
[`artifact-lifecycle.md`](artifact-lifecycle.md).

## Ship Criteria

Create a specialist package only when `decision.json` says `ship`.

For a newly produced package, `artifact.json.lifecycle_manifest` must name the
adjacent lifecycle sidecar and `factory-run publish-check` must validate it.
Legacy packages without a sidecar remain inspectable with an explicit warning;
do not invent missing identity to silence that warning.

Do not package:

- exploratory runs
- failed candidates
- candidates without baseline comparison
- candidates that require a moving eval
- candidates whose artifact path cannot be resolved
