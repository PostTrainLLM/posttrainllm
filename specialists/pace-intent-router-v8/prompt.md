# Pace Intent Router — classification prompt

This model is a classifier, not a generative model. It does not use a
prompt in the traditional sense. The input is a raw user transcript
(byte-level encoded, max 128 bytes) and the output is one of 7 class
labels.

## Input format

```
<raw user transcript, byte-level encoded, max 128 bytes>
```

## Output format

```
<single class label from: chitchat, pureKnowledge, screenDescription,
screenAction, research, phoneLargeModel, unknown>
```

## Class definitions

- **chitchat**: Greetings, thanks, goodbyes, social filler. e.g. "hi
  pace", "thanks", "how are you"
- **pureKnowledge**: Factual questions answerable without screen
  context. e.g. "what is HTML", "explain DNS"
- **screenDescription**: User wants a description of what's on screen.
  e.g. "what am I looking at", "what's on the screen"
- **screenAction**: User wants Pace to do something via the action
  layer. e.g. "click the save button", "open Safari"
- **research**: Multi-step research turn. e.g. "research quantum
  computing", "compare AWS vs GCP"
- **phoneLargeModel**: Explicit escalation request. e.g. "use the big
  model", "phone a large model"
- **unknown**: Classifier could not confidently assign a class. The
  caller must run the full pipeline.

## Decision boundaries (Pace-specific)

These boundaries are encoded in the synthetic training corpus and are
what the model learns. A general LLM does not know these:

- "turn on lights" = **unknown** (Pace can't control lights)
- "turn on volume" = **screenAction** (Pace can control volume)
- "what can you do" = **pureKnowledge** (not unknown — it's a question
  about Pace itself)
- "research HTML" = **research** (not pureKnowledge — the word
  "research" triggers the research lane)
- "I researched HTML yesterday" = **pureKnowledge** (past tense — not
  a research request)
