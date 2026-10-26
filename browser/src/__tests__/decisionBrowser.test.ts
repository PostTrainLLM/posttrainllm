import { describe, expect, it } from "vitest";
import {
  canonical,
  boundDecisionContract,
  decisionItem,
  selectedPrediction,
  tokenIds,
} from "../specialists/decision-input";

describe("portable decision contracts", () => {
  it("rejects integer-index labels instead of silently changing Python prompt order", () => {
    expect(() =>
      decisionItem({ question: "Choose", options: { "2": "two", "1": "one" } }),
    ).toThrow(/reorder/);
    expect(() =>
      decisionItem({
        question: "Choose",
        options: { A: "one", B: "two" },
        answer: 1,
      }),
    ).toThrow(/Answer/);
  });
  it("preserves non-index label insertion order and Python whitespace semantics", () => {
    const item = decisionItem({
      question: "\ufeff",
      options: { B: "two", A: "one" },
    });
    expect(Object.keys(item.options as object)).toEqual(["B", "A"]);
    expect(() =>
      decisionItem({ question: "\u0085", options: { A: "one", B: "two" } }),
    ).toThrow(/question/);
  });
  it("computes selected-label probabilities stably and supports explicit abstention", () => {
    expect(
      selectedPrediction(["A", "B"], [10000, 10000]).probabilities,
    ).toEqual({ A: 0.5, B: 0.5 });
    expect(
      selectedPrediction(["A", "B"], [10000, 10000], 0.6).label,
    ).toBeNull();
    expect(() => selectedPrediction(["A", "B"], [1, Infinity])).toThrow();
    expect(() => selectedPrediction(["A", "B"], [1, 2], "0.5")).toThrow();
  });
  it("rejects over-limit or invalid token IDs without truncation", () => {
    expect(() => tokenIds([1, 2, 3], 2)).toThrow(/over-limit/);
    expect(() => tokenIds([200000], 2)).toThrow();
    expect(() => tokenIds([-1], 2)).toThrow();
  });
  it("uses deterministic ASCII identity serialization matching the Python exporter", () => {
    expect(
      canonical({
        source: "a",
        files: { z: { bytes: 2, sha256: "b" }, a: 1 },
        format: "v1",
      }),
    ).toBe(
      '{"files":{"a":1,"z":{"bytes":2,"sha256":"b"}},"format":"v1","source":"a"}',
    );
  });
});

it("binds Unicode, numeric probes, prompt limits and option order to exact exported contract bytes", () => {
  const contract = {
    template: { prefix: "中文", suffix: "", vectors: [] },
    max_tokens: 256,
    probes: [
      { item: { options: { B: "two", A: "one" } }, logits: [1e-7, 2.0] },
    ],
  };
  const data = { ...contract, contract_json: JSON.stringify(contract) };
  expect(boundDecisionContract(data)).toBe(data.contract_json);
  expect(() => boundDecisionContract({ ...data, max_tokens: 512 })).toThrow(
    /contract/,
  );
  expect(() =>
    boundDecisionContract({
      ...data,
      template: { ...contract.template, prefix: "different" },
    }),
  ).toThrow(/contract/);
  expect(() => boundDecisionContract({ ...data, probes: [] })).toThrow(
    /contract/,
  );
  expect(() =>
    boundDecisionContract({
      ...data,
      probes: [
        { item: { options: { A: "one", B: "two" } }, logits: [1e-7, 2.0] },
      ],
    }),
  ).toThrow(/contract/);
});
