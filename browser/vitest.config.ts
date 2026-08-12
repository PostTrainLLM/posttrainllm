import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: [
        "src/tokenizer.ts",
        "src/datasets.ts",
        "src/gallery-schema.ts",
        "src/runtime_detect.ts",
        "src/storage.ts",
      ],
      thresholds: {
        // Measured Fleet adoption floor (2026-08-12). Raise these whenever
        // coverage improves; CI rejects a regression below the current truth.
        lines: 72,
        functions: 69,
        branches: 56,
        statements: 66,
      },
    },
  },
});
