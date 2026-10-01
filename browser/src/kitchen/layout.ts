/** Compact first-viewport composition; the complete article is the no-JS fallback.
 * Scene state stays in the DOM. Guide: docs/learn/llm-kitchen.md.
 */
export function compactScenes() {
  for (const stage of document.querySelectorAll<HTMLElement>(
    "[data-journey-stage]",
  )) {
    const scene = stage.querySelector<HTMLElement>(":scope > .scene-pair")!;
    const workspace = document.createElement("div");
    workspace.className = "scene-workspace";
    const lesson = document.createElement("div");
    lesson.className = "scene-lesson";
    const consolePanel = document.createElement("div");
    consolePanel.className = "scene-console";
    const notes = document.createElement("details");
    notes.className = "scene-notes";
    const summary = document.createElement("summary");
    summary.textContent = "Why this step matters";
    notes.append(summary);
    const children = [...stage.children];
    lesson.append(scene);
    const exercises = [
      ...stage.querySelectorAll<HTMLElement>(".exercise, .live-chat"),
    ];
    if (stage.id === "ingredients") {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-button sample-toggle";
      toggle.textContent = "Read full samples";
      toggle.setAttribute("aria-expanded", "false");
      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(expanded));
        exercises[0].dataset.fullSamples = String(expanded);
        toggle.textContent = expanded
          ? "Collapse samples"
          : "Read full samples";
      });
      exercises[0].querySelector("fieldset")!.before(toggle);
    }
    if (stage.id === "refine") {
      stage
        .querySelectorAll<HTMLElement>(".subchapter-anchor[id]")
        .forEach((anchor) => (anchor.id += "-reading"));
      const preferenceInspection = exercises[1].querySelector(".inspection");
      if (preferenceInspection) notes.append(preferenceInspection);
      const tasteEyebrow = exercises[1].querySelector(".eyebrow");
      if (tasteEyebrow) notes.append(tasteEyebrow!);
      const provenance = exercises[0].querySelector(".illustrative");
      if (provenance) notes.append(provenance);
      exercises[0].querySelector(".eyebrow")!.textContent =
        "Illustrative outputs · no training run";
      const tabs = document.createElement("div");
      tabs.className = "refine-tabs";
      tabs.setAttribute("role", "group");
      tabs.setAttribute("aria-label", "Post-training activities");
      const labels = ["Examples", "Taste test", "Serve"];
      const select = (index: number) => {
        exercises.forEach(
          (panel, position) => (panel.hidden = position !== index),
        );
        [...tabs.children].forEach((button, position) =>
          button.setAttribute("aria-pressed", String(position === index)),
        );
      };
      exercises.forEach((panel, index) => {
        panel.id ||= `refine-panel-${index}`;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary";
        button.textContent = labels[index];
        button.dataset.refinePanel = String(index);
        button.setAttribute("aria-controls", panel.id);
        button.addEventListener("click", () => {
          select(index);
          const hash = ["refine", "taste", "serve"][index];
          if (location.hash !== `#${hash}`) {
            history.pushState(null, "", `#${hash}`);
            window.dispatchEvent(new Event("kitchen-route"));
          }
        });
        tabs.append(button);
      });
      consolePanel.append(tabs, ...exercises);
      select(0);
    } else consolePanel.append(...exercises);
    for (const child of children) {
      if (
        child === scene ||
        exercises.includes(child as HTMLElement) ||
        child.matches(".eyebrow,h2,.journey-next")
      )
        continue;
      notes.append(child);
    }
    for (const panel of exercises) {
      panel
        .querySelectorAll(".small-note:not([id])")
        .forEach((note) => notes.append(note));
      const pair = panel.querySelector(".checkpoint-pair");
      if (pair) panel.querySelector(".inspection summary")!.after(pair);
    }
    if (stage.id === "chat") {
      const disclosure = consolePanel.querySelector(".chat-topline + p");
      if (disclosure) notes.append(disclosure);
    }
    // Expanded technical evidence remains available without dominating the initial view.
    consolePanel
      .querySelectorAll<HTMLDetailsElement>("details[open]")
      .forEach((detail) => (detail.open = false));
    if (stage.id === "chat") notes.append(document.querySelector(".sources")!);
    if (stage.id === "chat") {
      const context = document.createElement("details");
      context.className = "chat-context";
      context.open = true;
      const summary = document.createElement("summary");
      summary.textContent = "Kitchen / model connection";
      context.append(summary, scene, notes);
      lesson.append(context);
    } else lesson.append(notes);
    workspace.append(lesson, consolePanel);
    stage.querySelector("h2")!.after(workspace);
  }
  const controls = document.getElementById("scene-controls")!;
  document.querySelector(".journey-body")!.after(controls);
}
