import { projectAuthoredTemplate } from "../lib/template-markdown.mjs";
import { markdownLink } from "../lib/public-markdown";
import kitchenSource from "../pages/articles/how-to-cook-an-llm.astro?raw";
import sessionSource from "../pages/learn/session.astro?raw";
import {
  checkpoints,
  dinnerPrompt,
  ingredients,
  tasteResponses,
} from "../kitchen/model";
import { kitchenConfig } from "../kitchen/cook-model";
import { journey } from "./kitchen-journey";
import {
  inferenceSessions,
  type LessonSection,
} from "../learning/inference-content";
import { inferenceWeeks } from "../learning/inference-weeks";
import { learningUnits, learningCaseStudies } from "../learning/content";
import pathRegistry from "../../../docs/learn/path-registry.json";
import artifactJourney from "../../../docs/learn/artifact-journey.json";

function main(source: string) {
  const match = source.match(/<main\b[\s\S]*?<\/main>/);
  if (!match) throw new Error("Missing main source");
  return match[0];
}
function kitchenResolve(code: string): string | number | undefined {
  const values: Record<string, string | number> = {
    journey: "",
    "kitchenConfig.maxSteps": kitchenConfig.maxSteps,
    dinnerPrompt,
    "checkpoints[0].kitchen": checkpoints[0].kitchen,
    "checkpoints[0].method": checkpoints[0].method,
    "checkpoints[0].output": checkpoints[0].output,
    "checkpoints[0].evidence": checkpoints[0].evidence,
    "checkpoints[0].changed": checkpoints[0].changed,
    "tasteResponses.b": tasteResponses.b,
  };
  if (code in values) return values[code];
  if (code.startsWith("journey.map("))
    return journey
      .map((stop) =>
        markdownLink(stop.name, `/articles/how-to-cook-an-llm#${stop.id}`),
      )
      .join(" · ");
  if (code.startsWith("ingredients.map("))
    return ingredients
      .map(
        (sample) =>
          `### ${sample.title}\n\n${sample.id === "broken" ? "Dinner[NUL][replacement character]" : sample.text}`,
      )
      .join("\n\n");
  if (code.startsWith("checkpoints.map("))
    return checkpoints.map((checkpoint) => `- ${checkpoint.title}`).join("\n");
  if (code.startsWith('(["a", "b"] as const).map('))
    return ["a", "b"]
      .map((key) => `${key.toUpperCase()}: ${tasteResponses[key as "a" | "b"]}`)
      .join("\n\n");
}
function sections(items: LessonSection[]) {
  return items
    .flatMap((section) => [
      `### ${section.heading}`,
      ...(section.paragraphs ?? []),
      ...(section.bullets ?? []).map((item) => `- ${item}`),
      ...(section.code ? [`\`\`\`\n${section.code}\n\`\`\``] : []),
    ])
    .join("\n\n");
}
const current = inferenceSessions[0];
function sessionResolve(code: string): string | number | undefined {
  const values: Record<string, string | number> = {
    "current.number": current.number,
    "current.title": current.title,
    "current.summary": current.summary,
    "current.sourceHref": current.sourceHref,
    "current.sourceLabel": current.sourceLabel,
    "current.exercise": current.exercise,
    "current.workPlaceholder": current.workPlaceholder,
    "current.explanationPrompt": current.explanationPrompt,
    "current.masteryGate": current.masteryGate,
    "learningCaseStudies.length": learningCaseStudies.length,
    "pathRegistry.paths.length": pathRegistry.paths.length,
    '" "': " ",
    currentPublicLesson: sections(current.sections),
    currentWorkedExample: sections(current.workedExample),
    currentAnswerGuide: sections(current.answerGuide),
    currentDiagnostic: current.diagnosticPrompt ?? "",
    currentDiagnosticRepair: current.diagnosticRepair ?? "",
    currentPrediction: current.predictionPrompt,
    currentStarter: current.starterCode
      ? `\`\`\`python\n${current.starterCode}\n\`\`\``
      : "",
    currentChecks: current.checks.map((check) => `- ${check}`).join("\n"),
  };
  if (code in values) return values[code];
  if (code.startsWith("artifactJourney.stages.reduce("))
    return artifactJourney.stages.reduce(
      (count, stage) => count + stage.artifacts.length,
      0,
    );
  if (code.startsWith("inferenceSessions.map("))
    return inferenceSessions
      .map(
        (session) =>
          `### ${session.title}\n\nWeek 1 · Day ${session.day} · ${session.minutes} min · ready\n\n${session.objective}`,
      )
      .join("\n\n");
  if (code.startsWith("inferenceWeeks.slice(1).map("))
    return inferenceWeeks
      .slice(1)
      .flatMap((week) => [
        `### ${week.title}`,
        `Week ${week.week} · ${week.dates} · planned`,
        `**Before this:** ${week.prerequisites}`,
        `**Progression:** ${week.progression}`,
        ...(week.resources
          ? [
              `**Reading:** ${week.resources.map((resource) => markdownLink(resource.label, resource.href)).join(", ")}`,
            ]
          : []),
        `**Weekend evidence:** ${week.artifact}`,
        `**Pass criterion:** ${week.passCriterion}`,
        `**Boundary:** ${week.boundary}`,
      ])
      .join("\n\n");
  if (code.startsWith("learningUnits.map("))
    return learningUnits
      .flatMap((unit) => [
        `### ${unit.number}: ${unit.title}`,
        unit.summary,
        ...unit.lesson,
        `**Exercise:** ${unit.exercise}`,
        `**Mastery gate:** ${unit.masteryGate}`,
        markdownLink(unit.sourceLabel, unit.sourceHref),
      ])
      .join("\n\n");
  if (code.startsWith("learningCaseStudies.map("))
    return learningCaseStudies
      .flatMap((study) => [
        `### ${study.title}`,
        study.lesson,
        `**Exercise:** ${study.exercise}`,
        markdownLink(study.sourceLabel, study.sourceHref),
      ])
      .join("\n\n");
}
const sessionMain = main(sessionSource)
  .replace(
    /<div([^>]*data-current-lesson[^>]*)>[\s\S]*?<\/div>/,
    "<div$1>{currentPublicLesson}</div>",
  )
  .replace(
    /<div([^>]*data-current-worked-example[^>]*)>[\s\S]*?<\/div>/,
    "<div$1>{currentWorkedExample}</div>",
  )
  .replace(
    /<div([^>]*data-current-answer[^>]*)>[\s\S]*?<\/div>/,
    "<div$1>{currentAnswerGuide}</div>",
  )
  .replace(/<p data-current-diagnostic><\/p>/, "<p>{currentDiagnostic}</p>")
  .replace(
    /<p data-current-diagnostic-repair><\/p>/,
    "<p>{currentDiagnosticRepair}</p>",
  )
  .replace(/<p data-current-prediction><\/p>/, "<p>{currentPrediction}</p>")
  .replace(
    /<div[^>]*data-current-starter[^>]*><\/div>/,
    "<div>{currentStarter}</div>",
  )
  .replace(
    /<div[^>]*data-current-checks[^>]*><\/div>/,
    "<div>{currentChecks}</div>",
  )
  .replace(
    /Loading (?:recall schedule|checkpoints)…/g,
    "Browser-local progress is excluded from this public document.",
  );
export const learningMarkdown = {
  "/articles/how-to-cook-an-llm": projectAuthoredTemplate(
    main(kitchenSource),
    kitchenResolve,
  ),
  "/learn/session": projectAuthoredTemplate(sessionMain, sessionResolve),
};
