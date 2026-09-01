# CLI lab reference

`posttrainllm` is the runnable Mac-local side of the completed learning lab. It
retains the whole specialist loop without pretending that every historical
research command belongs in the everyday workflow:

```text
target -> data -> post-training -> eval -> package -> report
```

## Discover the surface safely

These commands only print metadata. They do not load a model, access the
network, or start training:

```bash
posttrainllm
posttrainllm --help
posttrainllm commands
posttrainllm commands --json
posttrainllm help factory-run
posttrainllm --version
```

Running the CLI without arguments or with `--help` prints the same short
overview and succeeds without side effects. `commands` is the complete catalog:
data preparation, post-training, evaluation, packaging, runtime, Mac-platform,
diagnostic, compatibility, and parked research commands. Each row has a stable
name, category, summary, invocation, and status. `commands --json` exposes the
same registry for scripts and learning tools.

The catalog is checked against the executable dispatch table by
`evals/cli-surface-smoke.sh`. A new command cannot silently become executable
without also becoming discoverable.

## Start with a bounded run

Inspect the plan before any training:

```bash
posttrainllm quickstart data.jsonl --dry-run
posttrainllm factory-run --help
```

Then follow the retained loop with the relevant command family:

| Stage      | Typical commands                                           | Durable output                            |
| ---------- | ---------------------------------------------------------- | ----------------------------------------- |
| Target     | `factory-run init`, `factory-run validate`                 | frozen target and run identity            |
| Data       | `prep-data`, `dedupe`, `filter`, `traces-to-data`          | dataset plus provenance                   |
| Post-train | `sft`, `dpo`, `distill`, `finetune`                        | adapter or candidate model                |
| Eval       | `eval-gate`, `eval-compare`, `eval-bfcl`, `eval-tau-bench` | normalized metrics and traces             |
| Package    | `bake-lora`, `export-mlx`, `validate`                      | validated specialist artifact             |
| Report     | `factory-run transition`, report compiler                  | ship, retry, redirect, or reject decision |

Use the [factory contract](factory/README.md) for the run schema and evidence
requirements. Use the [recipe registry](recipes/README.md) when selecting the
method, data, gate, regression checks, budget, and stop rule.

## Parked research commands

Research implementations remain available as learning assets, but the official
path makes their status visible:

```bash
posttrainllm experimental --help
posttrainllm experimental rome --help
posttrainllm experimental gptq --help
```

Historical top-level aliases such as `posttrainllm rome` still work for old
scripts. They are intentionally omitted from the default help and the official
catalog records the namespaced invocation instead.

## Exit-code contract

- `0`: the requested discovery or command operation succeeded.
- `1`: the command ran but its operation failed.
- `2`: usage error, missing argument, or unknown command.

Unknown commands point back to `posttrainllm commands`; they do not print an
unbounded help wall or attempt a fuzzy execution.

## Verification

The static contract is fast and does not compile Swift:

```bash
bash evals/cli-surface-smoke.sh
```

After building the binary, the same smoke also checks version output, JSON
schema, overview help, namespaced research help, and unknown-command exit
behavior. CI runs the static check in the eval job and the runtime check after
the macOS build.
