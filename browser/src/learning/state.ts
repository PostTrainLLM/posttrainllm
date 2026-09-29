import { learningUnits } from "./content";
import { inferenceSessions } from "./inference-content";
import {
  FOUNDATION_ROUTE,
  INFERENCE_ROUTE,
  learningRoutes,
  routeForSession,
  type LearningRouteId,
} from "./routes";

const LEARNING_SCHEMA_VERSION = 2;
const LEARNING_DB_NAME = "posttrainllm-learning";
const STORE_NAME = "workspace";
const STATE_KEY = "state";
const ALL_UNITS = [...learningUnits, ...inferenceSessions];
const LEARNING_MODULE_IDS = new Set([
  ...ALL_UNITS.map((unit) => unit.id),
  ...learningRoutes[INFERENCE_ROUTE].orderedSessionIds,
]);

export type LearningStatus = "reading" | "applied" | "verified";
export type ReviewResult = "pending" | "pass" | "needs-repair";

export interface RecallCheck {
  id: "plus-2" | "plus-7";
  dueDate: string;
  completedAt: string | null;
  prompt: string;
  response: string;
  result: ReviewResult;
  attempts?: Array<{
    response: string;
    result: Exclude<ReviewResult, "pending">;
    completedAt: string;
  }>;
}

export interface LearningCheckpoint {
  id: string;
  moduleId: string;
  createdAt: string;
  actualWork: string;
  prediction?: string;
  diagnostic?: string;
  explanation: string;
  repoConnection: string;
  immediateResult: ReviewResult;
  openQuestions: string;
  recalls: RecallCheck[];
}

export interface LearningWorkspaceState {
  schemaVersion: 2;
  updatedAt: string;
  currentRouteId: LearningRouteId;
  currentModuleId: string;
  status: LearningStatus;
  draft: LearningDraft;
  drafts: Record<string, LearningDraft>;
  checkpoints: LearningCheckpoint[];
}

export interface LearningDraft {
  diagnostic: string;
  prediction: string;
  actualWork: string;
  explanation: string;
  repoConnection: string;
  openQuestions: string;
}

const emptyDraft = (): LearningDraft => ({
  diagnostic: "",
  prediction: "",
  actualWork: "",
  explanation: "",
  repoConnection: "",
  openQuestions: "",
});

export interface LearningBackup {
  kind: "posttrainllm-learning-backup";
  exportedAt: string;
  state: LearningWorkspaceState;
}

export function emptyLearningState(now = new Date()): LearningWorkspaceState {
  return {
    schemaVersion: LEARNING_SCHEMA_VERSION,
    updatedAt: now.toISOString(),
    currentRouteId: INFERENCE_ROUTE,
    currentModuleId: learningRoutes[INFERENCE_ROUTE].defaultSessionId,
    status: "reading",
    draft: emptyDraft(),
    drafts: {},
    checkpoints: [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isReviewResult(value: unknown): value is ReviewResult {
  return value === "pending" || value === "pass" || value === "needs-repair";
}

function isValidRecall(value: unknown): boolean {
  return (
    isRecord(value) &&
    (value.id === "plus-2" || value.id === "plus-7") &&
    typeof value.dueDate === "string" &&
    (value.completedAt === null || typeof value.completedAt === "string") &&
    typeof value.prompt === "string" &&
    typeof value.response === "string" &&
    isReviewResult(value.result) &&
    (value.attempts === undefined ||
      (Array.isArray(value.attempts) &&
        value.attempts.every(
          (attempt) =>
            isRecord(attempt) &&
            typeof attempt.response === "string" &&
            (attempt.result === "pass" || attempt.result === "needs-repair") &&
            typeof attempt.completedAt === "string",
        )))
  );
}

function isValidCheckpoint(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.moduleId === "string" &&
    LEARNING_MODULE_IDS.has(value.moduleId) &&
    typeof value.createdAt === "string" &&
    typeof value.actualWork === "string" &&
    (value.prediction === undefined || typeof value.prediction === "string") &&
    (value.diagnostic === undefined || typeof value.diagnostic === "string") &&
    typeof value.explanation === "string" &&
    typeof value.repoConnection === "string" &&
    typeof value.openQuestions === "string" &&
    isReviewResult(value.immediateResult) &&
    Array.isArray(value.recalls) &&
    value.recalls.every(isValidRecall)
  );
}

function isValidLearningState(value: unknown): value is LearningWorkspaceState {
  if (!isRecord(value)) return false;
  if (value.schemaVersion !== LEARNING_SCHEMA_VERSION) return false;
  if (
    typeof value.updatedAt !== "string" ||
    (value.currentRouteId !== INFERENCE_ROUTE &&
      value.currentRouteId !== FOUNDATION_ROUTE) ||
    typeof value.currentModuleId !== "string" ||
    !LEARNING_MODULE_IDS.has(value.currentModuleId) ||
    routeForSession(value.currentModuleId) !== value.currentRouteId
  )
    return false;
  if (
    value.status !== "reading" &&
    value.status !== "applied" &&
    value.status !== "verified"
  )
    return false;
  if (!isRecord(value.draft)) return false;
  for (const key of [
    "diagnostic",
    "prediction",
    "actualWork",
    "explanation",
    "repoConnection",
    "openQuestions",
  ]) {
    if (typeof value.draft[key] !== "string") return false;
  }
  if (!isRecord(value.drafts)) return false;
  for (const [id, draft] of Object.entries(value.drafts)) {
    if (!LEARNING_MODULE_IDS.has(id) || !isRecord(draft)) return false;
    for (const key of [
      "diagnostic",
      "prediction",
      "actualWork",
      "explanation",
      "repoConnection",
      "openQuestions",
    ])
      if (typeof draft[key] !== "string") return false;
  }
  if (!Array.isArray(value.checkpoints)) return false;
  return value.checkpoints.every(isValidCheckpoint);
}

function normalizeState(value: unknown): LearningWorkspaceState {
  if (isValidLearningState(value)) return value;
  if (!isRecord(value) || value.schemaVersion !== 1)
    throw new Error(
      "The saved learning data is unsupported. Export or restore a valid backup before continuing.",
    );
  const oldId = value.currentModuleId;
  const oldDraft = value.draft;
  if (
    typeof oldId !== "string" ||
    routeForSession(oldId) !== FOUNDATION_ROUTE ||
    !isRecord(oldDraft) ||
    !["actualWork", "explanation", "repoConnection", "openQuestions"].every(
      (key) => typeof oldDraft[key] === "string",
    ) ||
    typeof value.updatedAt !== "string" ||
    (value.status !== "reading" &&
      value.status !== "applied" &&
      value.status !== "verified") ||
    !Array.isArray(value.checkpoints) ||
    !value.checkpoints.every(isValidCheckpoint)
  )
    throw new Error(
      "The saved learning data is invalid. Existing browser data was not replaced.",
    );
  const draft: LearningDraft = {
    diagnostic: "",
    prediction: "",
    actualWork: oldDraft.actualWork as string,
    explanation: oldDraft.explanation as string,
    repoConnection: oldDraft.repoConnection as string,
    openQuestions: oldDraft.openQuestions as string,
  };
  const migrated: LearningWorkspaceState = {
    schemaVersion: 2,
    updatedAt: value.updatedAt as string,
    currentRouteId: FOUNDATION_ROUTE,
    currentModuleId: oldId,
    status: value.status as LearningStatus,
    draft,
    drafts: { [oldId]: draft },
    checkpoints: value.checkpoints as unknown as LearningCheckpoint[],
  };
  if (!isValidLearningState(migrated))
    throw new Error(
      "The saved learning data is invalid. Existing browser data was not replaced.",
    );
  return migrated;
}

export function createCheckpoint(
  state: LearningWorkspaceState,
  result: Exclude<ReviewResult, "pending">,
  now = new Date(),
  timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone,
): LearningCheckpoint {
  const unit = ALL_UNITS.find((item) => item.id === state.currentModuleId);
  if (!unit) throw new Error("The selected learning module is not available.");
  const due = (days: number) =>
    addCalendarDays(localCalendarDate(now, timeZone), days);
  return {
    id: `${state.currentModuleId}-${now.getTime()}`,
    moduleId: state.currentModuleId,
    createdAt: now.toISOString(),
    actualWork: state.draft.actualWork.trim(),
    diagnostic: state.draft.diagnostic.trim(),
    prediction: state.draft.prediction.trim(),
    explanation: state.draft.explanation.trim(),
    repoConnection: state.draft.repoConnection.trim(),
    immediateResult: result,
    openQuestions: state.draft.openQuestions.trim(),
    recalls:
      result === "pass"
        ? [
            {
              id: "plus-2",
              dueDate: due(2),
              completedAt: null,
              prompt: unit.recallPrompts[0],
              response: "",
              result: "pending",
            },
            {
              id: "plus-7",
              dueDate: due(7),
              completedAt: null,
              prompt: unit.recallPrompts[1],
              response: "",
              result: "pending",
            },
          ]
        : [],
  };
}

export function applyCheckpoint(
  state: LearningWorkspaceState,
  checkpoint: LearningCheckpoint,
  now = new Date(),
): LearningWorkspaceState {
  return {
    ...state,
    updatedAt: now.toISOString(),
    status: checkpoint.immediateResult === "pass" ? "applied" : "reading",
    checkpoints: [
      checkpoint,
      ...state.checkpoints.filter((item) => item.id !== checkpoint.id),
    ],
  };
}

export function statusForModule(
  checkpoints: LearningCheckpoint[],
  moduleId: string,
): LearningStatus {
  const latest = checkpoints
    .filter((checkpoint) => checkpoint.moduleId === moduleId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
  if (!latest || latest.immediateResult === "needs-repair") return "reading";
  if (latest.recalls.some((recall) => recall.result === "needs-repair"))
    return "reading";
  if (
    latest.recalls.length === 2 &&
    latest.recalls.every((recall) => recall.result === "pass")
  )
    return "verified";
  return "applied";
}

export function selectLearningModule(
  state: LearningWorkspaceState,
  moduleId: string,
  now = new Date(),
): LearningWorkspaceState {
  const routeId = routeForSession(moduleId);
  if (!routeId)
    throw new Error("The selected learning session is not available.");
  const drafts = { ...state.drafts, [state.currentModuleId]: state.draft };
  return {
    ...state,
    updatedAt: now.toISOString(),
    currentRouteId: routeId,
    currentModuleId: moduleId,
    status: statusForModule(state.checkpoints, moduleId),
    draft: drafts[moduleId] ?? emptyDraft(),
    drafts,
  };
}

export function completeRecall(
  state: LearningWorkspaceState,
  checkpointId: string,
  recallId: RecallCheck["id"],
  response: string,
  result: Exclude<ReviewResult, "pending">,
  now = new Date(),
): LearningWorkspaceState {
  const checkpoints = state.checkpoints.map((checkpoint) => {
    if (checkpoint.id !== checkpointId) return checkpoint;
    return {
      ...checkpoint,
      recalls: checkpoint.recalls.map((recall) =>
        recall.id === recallId
          ? {
              ...recall,
              response: response.trim(),
              result,
              completedAt: now.toISOString(),
              attempts: [
                ...(recall.attempts ?? []),
                {
                  response: response.trim(),
                  result,
                  completedAt: now.toISOString(),
                },
              ],
            }
          : recall,
      ),
    };
  });
  return {
    ...state,
    updatedAt: now.toISOString(),
    status: statusForModule(checkpoints, state.currentModuleId),
    checkpoints,
  };
}

export function dueRecalls(
  state: LearningWorkspaceState,
  today = new Date(),
  timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone,
): Array<{
  checkpoint: LearningCheckpoint;
  recall: RecallCheck;
}> {
  const date = localCalendarDate(today, timeZone);
  return activeRecallCheckpoints(state).flatMap((checkpoint) =>
    checkpoint.recalls
      .filter((recall) => recall.result === "pending" && recall.dueDate <= date)
      .map((recall) => ({ checkpoint, recall })),
  );
}

export function activeRecallCheckpoints(
  state: LearningWorkspaceState,
): LearningCheckpoint[] {
  const seen = new Set<string>();
  return [...state.checkpoints]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .filter((checkpoint) => {
      if (seen.has(checkpoint.moduleId)) return false;
      seen.add(checkpoint.moduleId);
      return true;
    });
}

export function localCalendarDate(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

function addCalendarDays(date: string, days: number): string {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days))
    .toISOString()
    .slice(0, 10);
}

export function makeBackup(
  state: LearningWorkspaceState,
  now = new Date(),
): LearningBackup {
  return {
    kind: "posttrainllm-learning-backup",
    exportedAt: now.toISOString(),
    state,
  };
}

export function parseBackup(text: string): LearningBackup {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("This file is not valid JSON.");
  }
  if (!isRecord(value) || value.kind !== "posttrainllm-learning-backup") {
    throw new Error("This is not a PostTrainLLM learning backup.");
  }
  if (typeof value.exportedAt !== "string")
    throw new Error("The backup timestamp is missing or invalid.");
  return {
    kind: "posttrainllm-learning-backup",
    exportedAt: value.exportedAt,
    state: normalizeState(value.state),
  };
}

export function mergeLearningState(
  current: LearningWorkspaceState,
  incoming: LearningWorkspaceState,
  now = new Date(),
): LearningWorkspaceState {
  const checkpoints = new Map<string, LearningCheckpoint>();
  for (const checkpoint of [...current.checkpoints, ...incoming.checkpoints]) {
    const existing = checkpoints.get(checkpoint.id);
    if (!existing || checkpoint.createdAt >= existing.createdAt)
      checkpoints.set(checkpoint.id, checkpoint);
  }
  return {
    ...current,
    updatedAt: now.toISOString(),
    currentModuleId: incoming.currentModuleId || current.currentModuleId,
    currentRouteId: incoming.currentRouteId,
    status: incoming.status,
    draft: incoming.draft,
    drafts: { ...current.drafts, ...incoming.drafts },
    checkpoints: [...checkpoints.values()].sort((a, b) =>
      b.createdAt.localeCompare(a.createdAt),
    ),
  };
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Browser storage is unavailable."));
      return;
    }
    const request = indexedDB.open(LEARNING_DB_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME))
        request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("Could not open browser storage."));
  });
}

export async function loadLearningState(): Promise<LearningWorkspaceState> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readonly");
    const request = transaction.objectStore(STORE_NAME).get(STATE_KEY);
    request.onsuccess = () => {
      try {
        resolve(
          request.result === undefined
            ? emptyLearningState()
            : normalizeState(request.result),
        );
      } catch (error) {
        reject(error);
      }
    };
    request.onerror = () =>
      reject(request.error ?? new Error("Could not load learning progress."));
    transaction.oncomplete = () => database.close();
  });
}

export async function saveLearningState(
  state: LearningWorkspaceState,
): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).put(state, STATE_KEY);
    transaction.oncomplete = () => {
      database.close();
      resolve();
    };
    transaction.onerror = () => {
      database.close();
      reject(
        transaction.error ?? new Error("Could not save learning progress."),
      );
    };
  });
}
