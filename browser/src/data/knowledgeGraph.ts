/**
 * knowledgeGraph.ts — canonical public index for retained learning evidence.
 *
 * The tracked JSON registries remain the factual sources of truth. This module
 * normalizes them into one route contract so every study, experiment, recipe,
 * learning path, and buildable artifact gets exactly one canonical dossier.
 */
import attemptPayload from "../../../docs/attempts.json";
import artifactJourney from "../../../docs/learn/artifact-journey.json";
import pathRegistry from "../../../docs/learn/path-registry.json";
import recipeRegistry from "../../../docs/recipes/registry.json";
import studyRegistry from "../../../docs/studies/registry.json";
import {
  experimentLearningHref,
  experimentPublicHref,
  experimentRecipeHref,
} from "./experimentArchive";

const REPO = "https://github.com/PostTrainLLM/posttrainllm/blob/main/";

export type KnowledgeKind =
  "study" | "experiment" | "recipe" | "learning-path" | "learning-artifact";

export interface KnowledgeLink {
  label: string;
  href: string;
  kind?: string;
}

export interface KnowledgeFact {
  label: string;
  value: string;
}

export interface KnowledgeSection {
  title: string;
  paragraphs?: string[];
  items?: string[];
}

export interface KnowledgeRecord {
  id: string;
  kind: KnowledgeKind;
  kindLabel: string;
  title: string;
  description: string;
  status: string;
  canonicalPath: string;
  sourceRecord: string;
  facts: KnowledgeFact[];
  sections: KnowledgeSection[];
  sources: KnowledgeLink[];
  relations: KnowledgeLink[];
}

type Attempt = (typeof attemptPayload.attempts)[number];
type Recipe = (typeof recipeRegistry.recipes)[number];
type LearningPath = (typeof pathRegistry.paths)[number];
type JourneyStage = (typeof artifactJourney.stages)[number];
type LearningArtifact = JourneyStage["artifacts"][number];
type Study = (typeof studyRegistry.studies)[number];

const stages = artifactJourney.stages as JourneyStage[];
const artifactsWithStage = stages.flatMap((stage) =>
  stage.artifacts.map((artifact) => ({ artifact, stage })),
);

function humanize(value: string): string {
  return value.replaceAll("-", " ");
}

export function sourceHref(value: string): string {
  if (/^https?:\/\//u.test(value) || value.startsWith("/")) return value;
  const [path, fragment] = value.split("#", 2);
  if (path.startsWith("docs/") && path.endsWith(".md")) {
    return `/${path.slice(0, -3)}${fragment ? `#${fragment}` : ""}`;
  }
  return `${REPO}${value}${fragment ? `#${fragment}` : ""}`;
}

function uniqueLinks(links: KnowledgeLink[]): KnowledgeLink[] {
  return links.filter(
    (link, index) =>
      links.findIndex((candidate) => candidate.href === link.href) === index,
  );
}

function attemptMethodItems(attempt: Attempt): string[] {
  const items = [
    `Experiment family: ${humanize(attempt.family)}.`,
    `Record kind: ${humanize(attempt.kind)}.`,
  ];
  if ("objective" in attempt && attempt.objective) {
    items.push(`Objective: ${humanize(attempt.objective)}.`);
  }
  if ("methods" in attempt && attempt.methods?.length) {
    items.push(`Methods: ${attempt.methods.map(humanize).join(", ")}.`);
  }
  if ("bases" in attempt && attempt.bases?.length) {
    items.push(`Base models: ${attempt.bases.join(", ")}.`);
  }
  if ("data_rows" in attempt && attempt.data_rows != null) {
    items.push(`Recorded data rows: ${attempt.data_rows}.`);
  }
  return items;
}

export const experimentRecords: KnowledgeRecord[] = (
  attemptPayload.attempts as Attempt[]
).map((attempt) => ({
  id: attempt.id,
  kind: "experiment",
  kindLabel: `Experiment · ${humanize(attempt.family)}`,
  title: attempt.name,
  description: `${attempt.lesson} Retained outcome: ${humanize(attempt.status)}.`,
  status: humanize(attempt.status),
  canonicalPath: `/experiments/${attempt.id}`,
  sourceRecord: "docs/attempts.json",
  facts: [
    { label: "Outcome", value: humanize(attempt.status) },
    { label: "Family", value: humanize(attempt.family) },
    {
      label: "Evidence confidence",
      value: humanize(attempt.failure_reason_confidence),
    },
    { label: "Record", value: humanize(attempt.kind) },
  ],
  sections: [
    {
      title: "Evidence readout",
      paragraphs: [attempt.evidence],
    },
    {
      title: "What the attempt taught",
      paragraphs: [attempt.lesson],
    },
    ...(attempt.failure_reason
      ? [
          {
            title: "Why it stopped or stayed bounded",
            paragraphs: [attempt.failure_reason],
          },
        ]
      : []),
    {
      title: "Method and scope",
      items: attemptMethodItems(attempt),
    },
    {
      title: "Disposition",
      paragraphs: [
        attempt.next_action,
        "This retained disposition is historical evidence, not authorization to restart the experiment. A new run needs a fresh question, frozen evaluator, explicit resource budget, and scoped tracking issue.",
      ],
    },
  ],
  sources: uniqueLinks(
    [attempt.source, ...attempt.evidence_sources].map((path) => ({
      label: path,
      href: sourceHref(path),
    })),
  ),
  relations: uniqueLinks([
    {
      label: "Primary proof",
      href: experimentPublicHref(attempt),
      kind: "evidence",
    },
    {
      label: "Applicable recipe",
      href: experimentRecipeHref(attempt),
      kind: "recipe",
    },
    {
      label: "Learning path",
      href: experimentLearningHref(attempt),
      kind: "learning path",
    },
  ]),
}));

export const recipeRecords: KnowledgeRecord[] = (
  recipeRegistry.recipes as Recipe[]
).map((recipe) => ({
  id: recipe.id,
  kind: "recipe",
  kindLabel: "Reproducible recipe",
  title: recipe.title,
  description: `${recipe.target}. ${recipe.failure_mode}`,
  status: humanize(recipe.status),
  canonicalPath: `/recipes/${recipe.id}`,
  sourceRecord: "docs/recipes/registry.json",
  facts: [
    { label: "Status", value: humanize(recipe.status) },
    { label: "Learning path", value: humanize(recipe.learning_path) },
    {
      label: "Regression slices",
      value: String(recipe.regression_slices.length),
    },
    { label: "Execution", value: "Fresh experiment required" },
  ],
  sections: [
    { title: "Target", paragraphs: [recipe.target] },
    {
      title: "Failure this recipe addresses",
      paragraphs: [recipe.failure_mode],
    },
    { title: "Data contract", paragraphs: [recipe.data] },
    { title: "Method or policy", paragraphs: [recipe.method_or_policy] },
    {
      title: "Evaluation contract",
      paragraphs: [recipe.primary_eval],
      items: recipe.regression_slices,
    },
    {
      title: "Budget and stop rule",
      paragraphs: [recipe.resource_budget, recipe.stop_rule],
    },
    { title: "Decision rule", paragraphs: [recipe.decision_rule] },
    {
      title: "Learning exercise",
      paragraphs: [recipe.exercise, recipe.mastery_gate],
    },
  ],
  sources: uniqueLinks(
    [recipe.technique_path, ...recipe.evidence].map((path) => ({
      label: path,
      href: sourceHref(path),
    })),
  ),
  relations: [
    {
      label: humanize(recipe.learning_path),
      href: `/learn/paths/${recipe.learning_path}`,
      kind: "learning path",
    },
  ],
}));

export const learningPathRecords: KnowledgeRecord[] = (
  pathRegistry.paths as LearningPath[]
).map((path) => {
  const pathArtifacts = artifactsWithStage.filter(
    ({ stage }) => stage.path_id === path.id,
  );
  const pathRecipes = (recipeRegistry.recipes as Recipe[]).filter(
    (recipe) => recipe.learning_path === path.id,
  );
  return {
    id: path.id,
    kind: "learning-path",
    kindLabel: "Learning path",
    title: path.title,
    description: `${path.lab} Mastery is demonstrated when the learner can ${path.mastery_gate.charAt(0).toLowerCase()}${path.mastery_gate.slice(1)}`,
    status: "retained path",
    canonicalPath: `/learn/paths/${path.id}`,
    sourceRecord: "docs/learn/path-registry.json",
    facts: [
      { label: "Modules", value: String(path.sequence.length) },
      { label: "Prerequisites", value: String(path.prerequisites.length) },
      { label: "Recipes", value: String(pathRecipes.length) },
      { label: "Buildable artifacts", value: String(pathArtifacts.length) },
    ],
    sections: [
      {
        title: "Prerequisites",
        items: path.prerequisites.length
          ? path.prerequisites.map(humanize)
          : ["No earlier path is required."],
      },
      { title: "Learning sequence", items: path.sequence },
      { title: "Hands-on lab", paragraphs: [path.lab] },
      { title: "Mastery gate", paragraphs: [path.mastery_gate] },
      {
        title: "CLI surface",
        items: path.cli_commands.map((command) => `Run: ${command}`),
      },
    ],
    sources: path.anchors.map((anchor) => ({
      label: anchor,
      href: sourceHref(anchor),
    })),
    relations: [
      ...pathRecipes.map((recipe) => ({
        label: recipe.title,
        href: `/recipes/${recipe.id}`,
        kind: "recipe",
      })),
      ...pathArtifacts.map(({ artifact }) => ({
        label: artifact.title,
        href: `/learn/artifacts/${artifact.id}`,
        kind: "artifact",
      })),
    ],
  };
});

function artifactActionSections(
  artifact: LearningArtifact,
): KnowledgeSection[] {
  return [
    { title: "Build", paragraphs: [artifact.build.label] },
    { title: "Modify", paragraphs: [artifact.modify.label] },
    { title: "Tune", paragraphs: [artifact.tune.label] },
    { title: "Prove", paragraphs: [artifact.evaluate.label] },
    { title: "Package", paragraphs: [artifact.package.label] },
    {
      title: "CLI surface",
      items: artifact.cli_commands.map((command) => `Run: ${command}`),
    },
  ];
}

export const learningArtifactRecords: KnowledgeRecord[] =
  artifactsWithStage.map(({ artifact, stage }) => ({
    id: artifact.id,
    kind: "learning-artifact",
    kindLabel: `Buildable artifact · stage ${stage.order}`,
    title: artifact.title,
    description: artifact.summary,
    status: humanize(artifact.readiness),
    canonicalPath: `/learn/artifacts/${artifact.id}`,
    sourceRecord: "docs/learn/artifact-journey.json",
    facts: [
      { label: "Readiness", value: humanize(artifact.readiness) },
      { label: "Kind", value: artifact.kind },
      { label: "Workload", value: artifact.workload },
      { label: "Stage", value: stage.title },
    ],
    sections: [
      {
        title: "Artifact contract",
        paragraphs: [
          artifact.summary,
          `This ${artifact.kind} is classified as ${humanize(artifact.readiness)}. Workload guidance: ${artifact.workload}.`,
        ],
      },
      ...artifactActionSections(artifact),
    ],
    sources: uniqueLinks([
      ...artifact.anchors.map((anchor) => ({
        label: anchor,
        href: sourceHref(anchor),
      })),
      ...[
        artifact.build,
        artifact.modify,
        artifact.tune,
        artifact.evaluate,
        artifact.package,
      ].map((action) => ({
        label: action.label,
        href: sourceHref(action.href),
      })),
    ]),
    relations: [
      {
        label: stage.title,
        href: `/learn/paths/${stage.path_id}`,
        kind: "learning path",
      },
      ...(recipeRegistry.recipes as Recipe[])
        .filter((recipe) => recipe.learning_path === stage.path_id)
        .map((recipe) => ({
          label: recipe.title,
          href: `/recipes/${recipe.id}`,
          kind: "recipe",
        })),
    ],
  }));

const studyRelations: Record<string, KnowledgeLink[]> = {
  "apple-on-device-foundation-models": [
    {
      label: "Browser and Mac runtime path",
      href: "/learn/paths/browser-and-mac-runtime",
      kind: "learning path",
    },
  ],
  "castform-rl-finetune": [
    {
      label: "Evolution strategies",
      href: "/recipes/evolution-strategies",
      kind: "recipe",
    },
  ],
  "needle-2": [
    {
      label: "Needle 2 evaluation",
      href: "/recipes/needle2-evaluation",
      kind: "recipe",
    },
    {
      label: "Needle 2 selection ruler",
      href: "/learn/artifacts/needle-selection-ruler",
      kind: "artifact",
    },
  ],
  "parakeet-wgsl": [
    {
      label: "Parakeet browser ASR",
      href: "/recipes/parakeet-browser-asr",
      kind: "recipe",
    },
    {
      label: "Parakeet browser proof",
      href: "/artifacts/parakeet-wgsl-browser-asr",
      kind: "artifact",
    },
  ],
  "savante-aryabhata": [
    {
      label: "Post-training path",
      href: "/learn/paths/post-training",
      kind: "learning path",
    },
  ],
  "bonsai-2-27b": [
    {
      label: "Quantization and packaging",
      href: "/learn/paths/quantization-and-packaging",
      kind: "learning path",
    },
  ],
  qorl: [
    {
      label: "Evaluation and factory",
      href: "/learn/paths/evaluation-and-factory",
      kind: "learning path",
    },
  ],
  "inside-vllm": [
    {
      label: "Runtime and agents",
      href: "/learn/paths/runtime-and-agents",
      kind: "learning path",
    },
  ],
  "splash-mac-inference": [
    {
      label: "Runtime and agents",
      href: "/learn/paths/runtime-and-agents",
      kind: "learning path",
    },
  ],
};

export const studyRecords: KnowledgeRecord[] = (
  studyRegistry.studies as Study[]
).map((study) => ({
  id: study.id,
  kind: "study",
  kindLabel: study.kind,
  title: study.title,
  description: `${study.what_mattered} ${study.boundary}`,
  status: study.status,
  canonicalPath: `/studies/${study.id}`,
  sourceRecord: "docs/studies/registry.json",
  facts: [
    { label: "Disposition", value: study.status },
    { label: "Study class", value: study.kind },
    { label: "Reviewed", value: studyRegistry.updated },
    { label: "Evidence", value: "Tracked source record" },
  ],
  sections: [
    { title: "What mattered", paragraphs: [study.what_mattered] },
    { title: "What changed locally", paragraphs: [study.local_translation] },
    { title: "Evidence limits", paragraphs: [study.boundary] },
    {
      title: "Retained disposition",
      paragraphs: [
        study.next_action,
        "The action is retained as study context rather than an active backlog item. Any implementation, download, training run, or benchmark requires a fresh scoped question under the repository's experiment gate.",
      ],
    },
  ],
  sources: [
    {
      label: "Tracked study source",
      href: study.source_href,
    },
  ],
  relations: studyRelations[study.id] ?? [
    {
      label: "Complete learning map",
      href: "/learn",
      kind: "learning",
    },
  ],
}));

export const allKnowledgeRecords = [
  ...studyRecords,
  ...experimentRecords,
  ...recipeRecords,
  ...learningPathRecords,
  ...learningArtifactRecords,
];

export function getKnowledgeRecord(
  records: KnowledgeRecord[],
  id: string,
): KnowledgeRecord | undefined {
  return records.find((record) => record.id === id);
}

export function knowledgeWordCount(record: KnowledgeRecord): number {
  const text = [
    record.title,
    record.description,
    record.status,
    ...record.facts.flatMap((fact) => [fact.label, fact.value]),
    ...record.sections.flatMap((section) => [
      section.title,
      ...(section.paragraphs ?? []),
      ...(section.items ?? []),
    ]),
    ...record.sources.map((source) => source.label),
    ...record.relations.map((relation) => relation.label),
  ].join(" ");
  return text.trim().split(/\s+/u).filter(Boolean).length;
}
