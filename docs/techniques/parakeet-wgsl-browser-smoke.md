# parakeet.wgsl browser smoke

Review date: 2026-09-01
Decision: **validated browser-ASR proof; advance to a controlled comparison,
but do not integrate yet**.

## What was tested

The bounded smoke used upstream source revision
`8f654eedd8a19fec48cbbe57f9f3a972fedc96e3`, npm package `1.0.1`, and the
package's public demo/API boundary. The runtime selected NVIDIA Parakeet TDT
0.6B v2 revision `ae9ad07059c7c739ffaf932226a8fe64ae2620b0` through FP16 manifest
SHA-256 `11a359db3d050fd82b002c745b24a5280f3ff13a76834b548df671c95c786c65`.

The source is MIT licensed. The separately hosted converted model package is
CC BY 4.0. No model weights, generated cache, or upstream dependency was added
to this repository.

The real-browser run used Chrome on the Apple/Metal adapter. Capability
selection reported FP16, fixed 32-lane subgroup kernels, no fallback adapter,
and no warnings. The input was upstream's public 3,091,941-byte Kennedy MP3,
SHA-256 `dc12e3163c0da5f7fdfbfa4b4dfd0219d0d1c6c432d98c3b4a173829419f6f3f`,
with 1,030.486875 seconds of audio.

## Result

The first inference after the cold model load transcribed 17m 10s of audio in
7.225 seconds, or 142.6x real-time. Three subsequent warm runs took 7.80,
7.68, and 7.749 seconds (132.1x, 134.2x, and 133.0x real-time).

The repeated warm transcript was identical across runs: 11,661 characters,
SHA-256 `d857a2e16257841a1db12a2314209521d57be5b62af15cd0ba7906ac9f1615e4`.
That establishes runtime repeatability, not accuracy. The transcript was
coherent but visibly imperfect, including proper-name errors, phrase errors,
and duplicated phrases. No reference transcript or WER scorer was used in
this smoke.

The browser cached 29 verified assets totaling 405,252,493 bytes. Runtime
diagnostics reported:

- 405,063,936 packed model-download bytes;
- 404,930,560 model-runtime GPU bytes;
- 413,583,616 steady model GPU bytes;
- a 92,406,272-byte activation arena;
- 30,740,480 feature-staging bytes;
- 8,650,752 transient weight-scratch bytes.

These are component metrics, not a unified browser peak-RSS measurement. The
cold path started from a zero-byte cache. Polling observed 10.9% download after
about 10 seconds, 55.5% after about 40 seconds, inference by about 71 seconds,
and a completed result by about 91 seconds. Those are bounds rather than a
precise cold-start timer; the package's `totalMs` excludes download and model
initialization.

During a monitored warm transcription, Chrome emitted only a localhost worker
asset request and a local `blob:` request. No external request was observed.
This supports the package's local-after-download claim for the exercised path,
within the scope of main-tab DevTools observation.

The compact receipt is
`evals/parakeet-wgsl/bounded-browser-smoke-v1.json`.

## Decision

This is a successful adoption smoke. parakeet.wgsl is now a serious candidate
for optional browser audio ingestion: it works through the published package,
uses the right Apple WebGPU features, is dramatically faster than real-time on
the public long-form sample, and reuses a verified local cache.

It is not yet the selected ASR layer. The next justified experiment is a small,
shared, reference-transcribed set against the qualified Mac-native WhisperKit
baseline, covering exact domain terms, WER, cold/warm UX, Chrome and Safari,
and browser memory. The 386.5 MiB first download must remain explicit and
optional. A full LibriSpeech reproduction or production integration remains a
separate scope.
