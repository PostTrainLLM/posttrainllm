// astro.config.mjs — posttrainllm browser frontend.
//
// Astro wraps Vite, so the existing `?raw` WGSL imports from ../webgpu and the
// `new Worker(new URL("./worker.ts", import.meta.url))` pattern in src/main.ts
// continue to work via the standard Vite resolver. The build output directory
// is `dist/` (Astro default), which matches what Cloudflare Pages expects per
// docs/integrations/deploy.md, so the deploy contract is unchanged.
//
// Cross-origin isolation headers (COOP/COEP) MUST be set on the dev server —
// without them SharedArrayBuffer is unavailable and the multi-threaded WASM
// build fails to initialize. Production sets the same headers via
// browser/public/_headers (Cloudflare Pages copies that file verbatim).
//
// MDX integration is wired up so future devlog entries can be authored as
// `.mdx` files with embedded interactive Astro components. The existing
// devlog.html is migrated as a static page in this pass — converting its
// content to MDX is a future refactor, not gated on this turn.

import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  // Canonical origin — powers <link rel="canonical">, the sitemap, and OG URLs.
  site: "https://posttrainllm.com",

  // dist/ is the default Astro output dir; declared here for documentation.
  outDir: "./dist",

  // build.format = "file" emits dist/roadmap.html instead of
  // dist/roadmap/index.html, matching the legacy Vite output shape so the
  // existing audit scripts (which hit /roadmap.html) and any external
  // links/social cards keep resolving.
  // inlineStylesheets: "always" pushes per-page CSS into <style> tags inside
  // the HTML envelope, eliminating the index.<hash>.css render-blocker
  // psi-swarm flagged (~284ms desktop / ~1.6s mobile-slow). The h1 hero
  // (LCP element) lands in the first byte instead of waiting on a second
  // network round-trip for the stylesheet.
  build: { format: "file", inlineStylesheets: "always" },

  // Redirect docs that moved to docs/archive/ so the original URLs keep
  // working. Same for the doc that was split into a sub-folder.
  // These are static 301-style redirects emitted as small HTML pages by
  // the SSG build.
  redirects: {
    "/docs/annotated_transcript": "/docs/archive/annotated_transcript",
    "/docs/parked_multi_model": "/docs/archive/parked_multi_model",
    "/docs/shared_vs_native": "/docs/archive/shared_vs_native",
    "/docs/evaluation": "/docs/audits/validation_report",
    "/docs/watch_the_model_think": "/docs/techniques/interpretability",
    "/docs/phase_9_10_status": "/docs/roadmap/blockers",
    "/docs/single_machine_roadmap": "/docs/roadmap",
    "/docs/training_phases": "/docs/training",

    // Topic grouping of the flat docs/ top level.
    "/docs/learning/new-things": "/docs/learn/new-things",
    "/docs/DRILLDOWN": "/docs/sessions/DRILLDOWN",
    "/docs/RETROSPECTIVE": "/docs/sessions/RETROSPECTIVE",
    "/docs/audit_2026": "/docs/audits/audit_2026",
    "/docs/benchmark_first_run": "/docs/performance/benchmark_first_run",
    "/docs/benchmark_harness_design":
      "/docs/performance/benchmark_harness_design",
    "/docs/cold_start_results": "/docs/performance/cold_start_results",
    "/docs/constrained_generation": "/docs/techniques/constrained_generation",
    "/docs/continue_provider": "/docs/integrations/continue_provider",
    "/docs/cpu_speedup_results": "/docs/performance/cpu_speedup_results",
    "/docs/cpu_utilization_research":
      "/docs/performance/cpu_utilization_research",
    "/docs/data_perf": "/docs/performance/data_perf",
    "/docs/deploy": "/docs/integrations/deploy",
    "/docs/determinism": "/docs/performance/determinism",
    "/docs/distillation": "/docs/techniques/distillation",
    "/docs/docs-quality-audit": "/docs/audits/docs-quality-audit",
    "/docs/evolution_strategies": "/docs/techniques/evolution_strategies",
    "/docs/exactness-completion-audit":
      "/docs/audits/exactness-completion-audit",
    "/docs/fa2_backward_notes": "/docs/performance/fa2_backward_notes",
    "/docs/fa2_forward_notes": "/docs/performance/fa2_forward_notes",
    "/docs/feature_audit_2026_05_31": "/docs/audits/feature_audit_2026_05_31",
    "/docs/galore_and_stability": "/docs/techniques/galore_and_stability",
    "/docs/github_data_integration":
      "/docs/integrations/github_data_integration",
    "/docs/gradient_checkpointing_results":
      "/docs/performance/gradient_checkpointing_results",
    "/docs/hf_datasets_integration":
      "/docs/integrations/hf_datasets_integration",
    "/docs/history-coverage-audit": "/docs/audits/history-coverage-audit",
    "/docs/interpretability": "/docs/techniques/interpretability",
    "/docs/kv_cache_optimization": "/docs/performance/kv_cache_optimization",
    "/docs/lm_eval_integration": "/docs/integrations/lm_eval_integration",
    "/docs/lora_guide": "/docs/techniques/lora_guide",
    "/docs/memory_tradeoffs": "/docs/performance/memory_tradeoffs",
    "/docs/model_guide": "/docs/guides/model_guide",
    "/docs/moe": "/docs/techniques/moe",
    "/docs/mtp": "/docs/techniques/mtp",
    "/docs/online_softmax_in_attention":
      "/docs/performance/online_softmax_in_attention",
    "/docs/optimizers": "/docs/techniques/optimizers",
    "/docs/pace-handoff-2026-06-10": "/docs/sessions/pace-handoff-2026-06-10",
    "/docs/peft_variants": "/docs/techniques/peft_variants",
    "/docs/perf_audit_mlxfast_tied":
      "/docs/performance/perf_audit_mlxfast_tied",
    "/docs/perf_quest": "/docs/performance/perf_quest",
    "/docs/perf_research": "/docs/performance/perf_research",
    "/docs/performance": "/docs/performance/performance",
    "/docs/planner-lock-2026-06-19": "/docs/sessions/planner-lock-2026-06-19",
    "/docs/precision": "/docs/techniques/precision",
    "/docs/pruning": "/docs/techniques/pruning",
    "/docs/qa_log": "/docs/sessions/qa_log",
    "/docs/quantization_expansion": "/docs/techniques/quantization_expansion",
    "/docs/session_2026_05_31": "/docs/sessions/session_2026_05_31",
    "/docs/session_retrospective": "/docs/sessions/session_retrospective",
    "/docs/specialist_v1_findings": "/docs/sessions/specialist_v1_findings",
    "/docs/speculative_heads": "/docs/techniques/speculative_heads",
    "/docs/streaming_llm_kivi": "/docs/techniques/streaming_llm_kivi",
    "/docs/study_guide": "/docs/guides/study_guide",
    "/docs/test-coverage": "/docs/audits/test-coverage",
    "/docs/training_guide": "/docs/guides/training_guide",
    "/docs/v11-baselines-2026-06-09": "/docs/sessions/v11-baselines-2026-06-09",
    "/docs/validation_report": "/docs/audits/validation_report",
    "/docs/wwdc-2026-impact": "/docs/sessions/wwdc-2026-impact",
    "/docs/yoco_results": "/docs/performance/yoco_results",
  },

  integrations: [
    mdx(),
    sitemap({ customPages: ["https://posttrainllm.com/docs/"] }),
  ],

  server: {
    // Dev-server COOP/COEP mirror of public/_headers for production parity.
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },

  vite: {
    // Fleet standard (VoidZero ecosystem) — Lightning CSS as the CSS
    // transformer + minifier. Already bundled in Vite, just needs opting in.
    css: { transformer: "lightningcss" },
    build: { cssMinify: "lightningcss" },
    // Astro defaults Vite's envPrefix to "PUBLIC_" only. Our analytics
    // shim reads VITE_POSTHOG_KEY (the Vite-standard prefix), and the
    // GitHub Actions secret is named accordingly. Without this override,
    // Astro/Vite doesn't inline `import.meta.env.VITE_POSTHOG_KEY` and
    // Rollup tree-shakes the entire posthog.init() branch as dead code —
    // the bundle ends up with only the "Analytics disabled" cold path.
    envPrefix: ["PUBLIC_", "VITE_"],
    server: {
      // The WGSL kernels live in ../webgpu (shared Phase 5 location), one
      // level above this Astro root — allow the dev server to serve files
      // from there via the ?raw imports in webgpu/kernels.ts / ops.ts.
      fs: { allow: [".."] },
      headers: {
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
      },
    },
    preview: {
      headers: {
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
      },
    },
  },
});
