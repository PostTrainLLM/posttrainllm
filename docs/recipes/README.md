# posttrainllm Recipes

Copy-paste workflows for using posttrainllm specialists outside the core CLI.

For the complete closed lab contract, use
[`registry.json`](registry.json). It accounts for every retained technique and
records target, failure mode, data, method, primary and regression evals,
resource budget, stop rule, decision rule, evidence, learning exercise, and
mastery gate. The public [`/recipes`](https://posttrainllm.com/recipes) page
renders the full registry.

## Available recipes

| Recipe | Use it when |
|---|---|
| [Function-calling distillation](distillation-fc.md) | You want to distill a small tool-calling specialist and score it with BFCL. |
| [ScaleDown specialist](b25-scaledown.md) | You want an extractive context-compression specialist. |
| [smolagents specialist](cookbook-smolagents.md) | You want a posttrainllm model behind a Hugging Face smolagents tool-calling agent. |
| [Pydantic AI specialist](cookbook-pydantic-ai.md) | You want structured outputs from a posttrainllm-backed Pydantic AI agent. |
| [Personal code specialist](cookbook-personal-code-specialist.md) | You want a per-repo posttrainllm model wired into Continue.dev or Aider. |
| [Character specialist](cookbook-character-specialist.md) | You want a free local NPC, persona, or brand-voice specialist recipe. |
| [Eval gate (CI / pre-commit)](eval-gate.md) | You want `posttrainllm eval-gate` to fail a merge when a specialist regresses, on your own Mac runner. |

## Closed-Lab Rule

These recipes are ready learning and reproduction assets. They do not authorize
background AI work or imply an unfinished historical experiment. After the
owner begins learning, a recipe becomes active only through a fresh question,
new experiment ID, frozen ruler, and bounded resource plan.
