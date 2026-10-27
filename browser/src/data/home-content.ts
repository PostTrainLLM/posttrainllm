import { workbenchContent } from "@saas-maker/templates/schema";
import { z } from "astro/zod";
import json from "../content/home.json";
import attemptLedger from "../../../docs/attempts.json";
import { macReleaseRecord } from "./mac-release";
import { evaluateMacRelease, macReleaseStatusLabel } from "../lib/mac-release";

const counts = {
  attemptCount: attemptLedger.attempts.length,
  workedCount: attemptLedger.attempts.filter((a) => a.status === "worked")
    .length,
  caveatCount: attemptLedger.attempts.filter(
    (a) => a.status === "worked-with-caveat",
  ).length,
  nonPositiveCount: attemptLedger.attempts.filter(
    (a) => !["worked", "worked-with-caveat"].includes(a.status),
  ).length,
};
const homeContent = workbenchContent.extend({
  directories: z.array(
    z
      .object({
        id: z.string(),
        title: z.string(),
        lede: z.string(),
        links: z.array(
          z.object({ label: z.string(), href: z.string() }).strict(),
        ),
      })
      .strict(),
  ),
  head: z.object({ jsonLd: z.array(z.string()).length(2) }).strict(),
  sources: z.array(
    z
      .object({ section: z.string(), label: z.string(), href: z.string() })
      .strict(),
  ),
});
export const content = homeContent.parse({
  ...json,
  page: {
    ...json.page,
    jsonLd: json.head.jsonLd.map((raw) => JSON.parse(raw)),
  },
  hero: {
    ...json.hero,
    status: {
      label: `native Mac app · ${macReleaseStatusLabel(evaluateMacRelease(macReleaseRecord))}`,
      href: "/download",
    },
  },
  sections: json.sections.map((section) => ({
    ...section,
    blocks: section.blocks.map((block) => ({
      ...block,
      ...("lede" in block && {
        lede: block.lede?.replace(/\{(\w+)\}/g, (_, key: string) => {
          if (!(key in counts)) throw new Error(`Unknown home count: ${key}`);
          return String(counts[key as keyof typeof counts]);
        }),
      }),
    })),
  })),
});
