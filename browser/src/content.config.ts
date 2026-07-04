import { defineCollection } from "astro/content/config";

const docs = defineCollection({
  // The /docs pages use import.meta.glob directly so they can preserve the
  // repo's markdown paths. Keep this collection explicitly defined to avoid
  // Astro auto-generating it, but do not load the copied markdown twice.
  loader: {
    name: "empty-docs-collection",
    load: async ({ store }) => {
      store.clear();
    },
  },
});

export const collections = { docs };
