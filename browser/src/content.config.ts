import { defineCollection } from "astro/content/config";
import { glob } from "astro/loaders";

const docs = defineCollection({
  loader: glob({
    base: "./src/content/docs",
    pattern: "**/*.md",
    _legacy: true,
  }),
});

export const collections = { docs };
