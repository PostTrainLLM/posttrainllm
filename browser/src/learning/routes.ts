export const INFERENCE_ROUTE = "inference-systems-13w";
export const FOUNDATION_ROUTE = "ground-up";

export const inferenceWeekOneIds = Array.from(
  { length: 7 },
  (_, index) => `inference-w01-d${String(index + 1).padStart(2, "0")}`,
);

export const learningRoutes = {
  [INFERENCE_ROUTE]: {
    id: INFERENCE_ROUTE,
    title: "Inference systems · 13-week sprint",
    orderedSessionIds: inferenceWeekOneIds,
    defaultSessionId: inferenceWeekOneIds[0],
  },
  [FOUNDATION_ROUTE]: {
    id: FOUNDATION_ROUTE,
    title: "Ground-up foundations",
    orderedSessionIds: [
      "functions-data-parameters",
      "loss-gradient-descent",
      "vectors-matrices-tensors",
      "nonlinear-networks-backprop",
      "paradigms-scaling",
      "tokens-embeddings-language",
      "attention-transformers",
      "training-mechanics",
      "post-training",
      "evals-rewards-factory",
    ],
    defaultSessionId: "functions-data-parameters",
  },
} as const;

export type LearningRouteId = keyof typeof learningRoutes;

export function routeForSession(id: string): LearningRouteId | null {
  if (learningRoutes[INFERENCE_ROUTE].orderedSessionIds.includes(id))
    return INFERENCE_ROUTE;
  if (
    (
      learningRoutes[FOUNDATION_ROUTE].orderedSessionIds as readonly string[]
    ).includes(id)
  )
    return FOUNDATION_ROUTE;
  return null;
}

export function resolveSessionUrl(search: string):
  | {
      routeId: LearningRouteId | null;
      sessionId: string | null;
      error: string | null;
    }
  | { routeId: null; sessionId: null; error: string } {
  const params = new URLSearchParams(search);
  const requestedRoute = params.get("route");
  const requestedSession = params.get("session");
  if (!requestedRoute && !requestedSession)
    return { routeId: null, sessionId: null, error: null };
  const routeId =
    requestedRoute ??
    (requestedSession ? routeForSession(requestedSession) : null);
  if (!routeId || !(routeId in learningRoutes))
    return {
      routeId: null,
      sessionId: null,
      error: "Unknown learning route. Choose a valid course below.",
    };
  const route = learningRoutes[routeId as LearningRouteId];
  if (
    requestedSession &&
    !(route.orderedSessionIds as readonly string[]).includes(requestedSession)
  )
    return {
      routeId: null,
      sessionId: null,
      error:
        "That session does not belong to this route. Choose a valid session below.",
    };
  return {
    routeId: routeId as LearningRouteId,
    sessionId: requestedSession,
    error: null,
  };
}
