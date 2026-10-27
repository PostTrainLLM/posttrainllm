export const journey = [
  { id: "ingredients", scene: "harvest", name: "Harvest", model: "Find data" },
  { id: "chopping", scene: "chop", name: "Chop", model: "Inspect tokens" },
  { id: "cleaning", scene: "clean", name: "Clean", model: "Prepare the batch" },
  { id: "base-recipe", scene: "cook", name: "Cook", model: "Pre-train" },
  {
    id: "refine",
    scene: "serve",
    name: "Refine & serve",
    model: "Post-train → infer",
  },
  { id: "chat", scene: "serve", name: "Talk", model: "Live inference" },
] as const;
