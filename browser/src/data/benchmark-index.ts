import replay from "./benchmarks/game-2048-pilot-v1.json";
export const measured = replay.models.flatMap((model) =>
  model.aggregate ? [{ ...model, aggregate: model.aggregate }] : [],
);
if (measured.length === 0)
  throw new Error(
    "2048 benchmark catalog requires at least one measured result",
  );
export const strongest = measured.reduce((best, model) =>
  model.aggregate.mean_score > best.aggregate.mean_score ? model : best,
);
