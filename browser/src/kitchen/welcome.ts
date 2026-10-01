/** Experience-first harvest mirrors the canonical ingredient controls.
 * Guide: docs/learn/llm-kitchen.md. No separate dataset or training state.
 */
export function initializeWelcome() {
  const opening = document.querySelector<HTMLElement>(".kitchen-opening")!;
  const crops = [
    ...opening.querySelectorAll<HTMLInputElement>("[data-opening-source]"),
  ];
  const canonical = [
    ...document.querySelectorAll<HTMLInputElement>("[data-ingredient]"),
  ];
  const names: Record<string, string> = {
    explanation: "Dinner recipe",
    conversation: "Conversation",
    code: "Code",
    duplicate: "Duplicate",
    broken: "Imported note",
    dairy: "Cheese recipe",
    weather: "Forecast",
  };
  const refresh = () => {
    const selected = canonical.filter((input) => input.checked);
    for (const input of crops) {
      input.checked =
        canonical.find((source) => source.value === input.dataset.openingSource)
          ?.checked ?? false;
      const crop = input.closest<HTMLElement>(".opening-crop")!;
      crop.querySelector(".crop-action")!.textContent = input.checked
        ? "In your basket"
        : "Add to basket";
      crop.querySelector(".crop-check")!.textContent = input.checked
        ? "✓"
        : "+";
    }
    opening.querySelector("#opening-count")!.textContent = selected.length
      ? `${selected.length} text ${selected.length === 1 ? "sample" : "samples"} in your basket.`
      : "Your basket is empty. Pick a sample above.";
    const tray = opening.querySelector("#opening-picked")!;
    tray.replaceChildren(
      ...selected.map((input) => {
        const chip = document.createElement("span");
        chip.textContent = names[input.value] ?? input.value;
        return chip;
      }),
    );
    const next = opening.querySelector<HTMLAnchorElement>(".start-journey")!;
    next.href = selected.length ? "#chopping" : "#welcome";
    next.setAttribute("aria-disabled", String(selected.length === 0));
    next.firstChild!.textContent = selected.length
      ? "To the cutting board "
      : "Pick a sample to continue ";
    opening.querySelector("#opening-status")!.textContent = selected.length
      ? selected.some(
          (source) => source.value === "dairy" || source.value === "weather",
        )
        ? "Would every picked sample help a dairy-free dinner assistant? You can keep it and review at the sink."
        : "Your choices will become the training text. No model weights have changed."
      : "Choose what would help your dinner assistant learn. No weights have changed.";
  };
  for (const input of crops)
    input.addEventListener("change", () => {
      const source = canonical.find(
        (source) => source.value === input.dataset.openingSource,
      )!;
      source.checked = input.checked;
      source.dispatchEvent(new Event("change", { bubbles: true }));
      const crop = input.closest<HTMLElement>(".opening-crop")!;
      crop.classList.remove("crop-picked");
      void crop.offsetWidth;
      if (input.checked) crop.classList.add("crop-picked");
      refresh();
    });
  for (const input of canonical) input.addEventListener("change", refresh);
  opening
    .querySelector(".start-journey")!
    .addEventListener("click", (event) => {
      if (!canonical.some((input) => input.checked)) {
        event.preventDefault();
        event.stopPropagation();
        crops[0].focus();
      }
    });
  opening.querySelector<HTMLElement>(".opening-crops")!.hidden = false;
  refresh();
  return refresh;
}
