/// Gallery manifest schema — single source of truth shared between the
/// Node-side tooling scripts (finalize, score, train_gallery_one,
/// inspect) and the browser-side leaderboard / gallery dialog code.
///
/// File location: `browser/public/gallery/manifest.json`. The browser
/// loads it once at boot; the Node tooling rewrites it after every
/// gallery refresh. Schema changes here ripple to both halves.

/** One entry in the manifest's `models` array — a single gallery model.
 *  The lifecycle: `train_gallery_one` produces the raw artefacts +
 *  initial entry; `finalize_gallery` packs the .bin file and stamps
 *  the file metadata; `score_gallery` / `score_gallery_tasks` write
 *  the benchmark scores. */
export interface GalleryModel {
  /** stable id used as the manifest key + the `<select>` value. */
  id: string;
  /** Display name in the gallery dialog. */
  name: string;
  /** Emoji shown next to the name — purely cosmetic. */
  icon?: string;
  /** One-line blurb shown under the name. */
  blurb?: string;
  /** Where the corpus came from (human-readable). */
  corpus?: string;
  /** Optional public URL to the corpus source. */
  corpusUrl?: string;
  /** Filename of the fp16 weight bin under `browser/public/gallery/`. */
  file: string;
  /** Optional filename of the int4 variant (~4× smaller). Written by
   *  `finalize_gallery_int4`. Browser picks fp16 vs int4 at load time
   *  based on the numerics gate + user preference. Absent → fp16 only. */
  fileInt4?: string;
  /** Size of the published `.int4.bin` file in bytes. */
  fileInt4Bytes?: number;
  /** Display string like "9.6M" for the parameter count. */
  params?: string;
  /** Numeric parameter count — what the leaderboard sorts on. */
  paramCount?: number;
  /** Final training loss as a display string (e.g. "1.22"). */
  trainLoss?: string;
  /** Number of training steps that produced this checkpoint. */
  steps?: number;
  /** A short generated sample used in the gallery preview. */
  sample?: string;
  /** Size of the published `.bin` file in bytes. */
  fileBytes?: number;
  /** Resident GPU memory the model needs at fp16 (display only). */
  gpuBytes?: number;
  /** Default prompt to put in the playground when the model loads. */
  prompt?: string;
  /** Wall-clock training time in ms (null if not measured). */
  trainWallMs?: number | null;
  /** Submission metadata — author + when + browser-trained flag. */
  submission?: GallerySubmission;
  /** Benchmark scores keyed by `Benchmark.id`. `null` = ran but
   *  incompatible (e.g. byte-level scorer + BPE model). Absence =
   *  hasn't been scored yet. */
  benchmarks?: Record<string, number | null>;
  /** B31 — artifact kind, so the unified gallery can mix browser-trained
   *  models with Mac-side HF/safetensors specialists. Values mirror the Swift
   *  `GalleryModelKind` raw values EXACTLY (one schema, two readers). Absent ⇒
   *  `browser-bin` (the historical default, a browser-loadable `.bin`). */
  kind?:
    | "browser-bin"
    | "mac-posttrainllm"
    | "mac-adapter"
    | "mac-gguf"
    | "mac-safetensors-hf";
  /** B31 — for adapter kinds (`mac-adapter`): the `id` of the base model it
   *  applies to. Should match another entry's `id` in the same manifest. */
  parent?: string;
  /** B31 — R2/remote object path for Mac-side artifacts not shipped under
   *  `browser/public/gallery/` (the gallery lists but can't load them). */
  r2_path?: string;
  /** B31 — freeform tags for gallery filtering (e.g. "specialist", "indic"). */
  tags?: string[];
}

/** Submission metadata for a single model. The `featured` flag marks
 *  manually-curated entries for the leaderboard front page. */
interface GallerySubmission {
  /** Display name of the submitter. */
  author: string;
  /** ISO 8601 timestamp of submission. */
  submittedAt: string;
  /** Did the model train entirely in-browser? Drives the
   *  "browser-trainable" badge on the leaderboard row. */
  browserTrained?: boolean;
  /** Was the model curated for the front-page highlight section? */
  featured?: boolean;
}

/** The whole manifest. `version` lets us evolve the schema without
 *  breaking older browser caches — bump when a non-backwards-compat
 *  field lands and have the reader gracefully degrade. */
export interface GalleryManifest {
  version: number;
  /** Optional top-of-page descriptor — shows above the gallery grid. */
  note?: string;
  /** All published models, in display order. */
  models: GalleryModel[];
}
