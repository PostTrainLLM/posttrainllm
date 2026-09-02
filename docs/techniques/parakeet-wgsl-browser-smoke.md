# parakeet.wgsl browser smoke

Review date: 2026-09-02
Decision: **paired quality and native-latency win; reject against the frozen 50x
short-clip throughput gate**.

## Reference-scored browser versus native result

The follow-up used eight fixed LibriSpeech `test-clean` rows spanning eight
speakers and chapters: 34.365 seconds and 82 normalized reference words. Both
arms received the identical audio, references, normalization, and seeded
execution order. The candidate was the official Parakeet TDT 0.6B v3 browser
engine at source revision `ab738c92b8a6af0dcdfe51dddd062427a5ec7689`; the
incumbent was WhisperKit CLI v1.1.0 with the local Whisper large-v3 turbo Core
ML model. The frozen protocol is
`evals/verified-wins/parakeet-asr-v1.json`.

| Measure | Browser Parakeet v3 | Native WhisperKit | Result |
|---|---:|---:|---|
| Word errors / 82 | **0** | 7 | browser wins |
| WER | **0.00%** | 8.54% | −8.54 points |
| Proper nouns | 4/4 | 4/4 | tied |
| Repetition events | 0 | 0 | tied |
| Total decode | **914.7 ms** | 3,211.8 ms | browser **3.51x faster** |
| Aggregate real-time factor | **37.57x** | 10.70x | browser wins |
| Median per-clip real-time factor | **33.84x** | 9.28x | below frozen 50x gate |

Chrome 151 selected the real Apple/Metal 3 adapter with FP16, subgroups, and
the experimental subgroup-matrix feature. It was neither fallback nor
software rendering. The browser downloaded 684,385,250 pinned model bytes and
made zero external requests during warm inference.

Three of four formal gates passed: WER stayed within two points (and in fact
won), repetitions did not regress, and the warm path stayed local. The
preregistered median throughput target did not: 33.84x is below 50x. These
short 2–7 second clips expose an approximately 80–100 ms fixed dispatch floor,
so they are a much harder throughput case than the earlier 17-minute smoke.
That is a systems lesson, not permission to replace the gate after seeing the
answer.

The compact result is
`evals/verified-wins/parakeet-asr-result-v1.json`. Raw transcripts, native JSON
reports, scores, adapter details, and request logs remain under the ignored
`runs/verified-wins/parakeet-browser-native-paired-v1/` directory; the tracked
result records their SHA-256 digests.

## Earlier long-form adoption smoke

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

That smoke correctly withheld the accuracy claim and led to the paired test
above. The controlled comparison now qualifies accuracy on its bounded fixture
and shows that browser Parakeet is faster than this native incumbent. It still
does not select a product ASR layer because the separately frozen 50x
short-clip gate failed. The 652.7 MiB v3 first download must remain explicit
and optional. A batching/long-form gate, Safari qualification, larger WER set,
or product integration would each be a new experiment rather than unfinished
work in this one.
