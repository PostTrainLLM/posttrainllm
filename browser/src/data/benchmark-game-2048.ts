import replay from "./benchmarks/game-2048-pilot-v1.json";
export const clientData = JSON.stringify(replay).replaceAll("<", "\\u003c");
export const measuredModels = replay.models.flatMap((model) =>
  model.aggregate ? [{ ...model, aggregate: model.aggregate }] : [],
);
export const specialist = replay.models.find(
  (model) => model.role === "specialist-candidate",
);
