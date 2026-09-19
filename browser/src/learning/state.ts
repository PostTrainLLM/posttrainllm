import { learningUnits } from "./content";

const LEARNING_SCHEMA_VERSION = 1;
const LEARNING_DB_NAME = "posttrainllm-learning";
const STORE_NAME = "workspace";
const STATE_KEY = "state";
const LEARNING_MODULE_IDS = new Set(learningUnits.map((unit) => unit.id));

export type LearningStatus = "reading" | "applied" | "verified";
export type ReviewResult = "pending" | "pass" | "needs-repair";

export interface RecallCheck {
  id: "plus-2" | "plus-7";
  dueDate: string;
  completedAt: string | null;
  prompt: string;
  response: string;
  result: ReviewResult;
}

export interface LearningCheckpoint {
  id: string;
  moduleId: string;
  createdAt: string;
  actualWork: string;
  explanation: string;
  repoConnection: string;
  immediateResult: ReviewResult;
  openQuestions: string;
  recalls: RecallCheck[];
}

export interface LearningWorkspaceState {
  schemaVersion: 1;
  updatedAt: string;
  currentModuleId: string;
  status: LearningStatus;
  draft: {
    actualWork: string;
    explanation: string;
    repoConnection: string;
    openQuestions: string;
  };
  checkpoints: LearningCheckpoint[];
}

export interface LearningBackup {
  kind: "posttrainllm-learning-backup";
  exportedAt: string;
  state: LearningWorkspaceState;
}

export function emptyLearningState(now = new Date()): LearningWorkspaceState {
  return {
    schemaVersion: LEARNING_SCHEMA_VERSION,
    updatedAt: now.toISOString(),
    currentModuleId: "functions-data-parameters",
    status: "reading",
    draft: {
      actualWork: "",
      explanation: "",
      repoConnection: "",
      openQuestions: "",
    },
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
    isReviewResult(value.result)
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
    typeof value.currentModuleId !== "string" ||
    !LEARNING_MODULE_IDS.has(value.currentModuleId)
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
    "actualWork",
    "explanation",
    "repoConnection",
    "openQuestions",
  ]) {
    if (typeof value.draft[key] !== "string") return false;
  }
  if (!Array.isArray(value.checkpoints)) return false;
  return value.checkpoints.every(isValidCheckpoint);
}

export function createCheckpoint(
  state: LearningWorkspaceState,
  result: Exclude<ReviewResult, "pending">,
  now = new Date(),
): LearningCheckpoint {
  const unit = learningUnits.find((item) => item.id === state.currentModuleId);
  if (!unit) throw new Error("The selected learning module is not available.");
  const due = (days: number) => {
    const date = new Date(now);
    date.setDate(date.getDate() + days);
    return date.toISOString().slice(0, 10);
  };
  return {
    id: `${state.currentModuleId}-${now.getTime()}`,
    moduleId: state.currentModuleId,
    createdAt: now.toISOString(),
    actualWork: state.draft.actualWork.trim(),
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
  const latest = checkpoints.find(
    (checkpoint) => checkpoint.moduleId === moduleId,
  );
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
  return {
    ...state,
    updatedAt: now.toISOString(),
    currentModuleId: moduleId,
    status: statusForModule(state.checkpoints, moduleId),
    draft: {
      actualWork: "",
      explanation: "",
      repoConnection: "",
      openQuestions: "",
    },
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
    const failed = result === "needs-repair";
    return {
      ...checkpoint,
      recalls: checkpoint.recalls
        .filter(
          (recall) =>
            !failed || recall.id === recallId || recall.result !== "pending",
        )
        .map((recall) =>
          recall.id === recallId
            ? {
                ...recall,
                response: response.trim(),
                result,
                completedAt: now.toISOString(),
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
): Array<{
  checkpoint: LearningCheckpoint;
  recall: RecallCheck;
}> {
  const date = today.toISOString().slice(0, 10);
  return state.checkpoints.flatMap((checkpoint) =>
    checkpoint.recalls
      .filter((recall) => recall.result === "pending" && recall.dueDate <= date)
      .map((recall) => ({ checkpoint, recall })),
  );
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
  if (!isValidLearningState(value.state)) {
    throw new Error("The backup version or learning data is unsupported.");
  }
  return value as unknown as LearningBackup;
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
    status: incoming.status,
    draft: incoming.draft,
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
    request.onsuccess = () =>
      resolve(
        isValidLearningState(request.result)
          ? request.result
          : emptyLearningState(),
      );
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
