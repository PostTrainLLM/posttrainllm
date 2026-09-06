import { describe, expect, it } from "vitest";
import type { MacReleaseRecord } from "../data/mac-release";
import { macReleaseRecord } from "../data/mac-release";
import { evaluateMacRelease } from "../lib/mac-release";

const eligibleRelease = (): MacReleaseRecord => ({
  ...macReleaseRecord,
  state: "available",
  artifactURL:
    "https://github.com/PostTrainLLM/posttrainllm/releases/download/v0.1.0/PostTrainLLM-0.1.0.dmg",
  sha256: "a".repeat(64),
  verification: {
    developerIdSigned: true,
    hardenedRuntime: true,
    notarized: true,
    stapled: true,
    gatekeeperAccepted: true,
    checksumVerified: true,
  },
});

describe("evaluateMacRelease", () => {
  it("publishes the shipped notarized candidate with its verified artifact", () => {
    expect(evaluateMacRelease(macReleaseRecord)).toMatchObject({
      version: "0.1.0",
      build: "1",
      state: "available",
      downloadable: true,
      artifactURL:
        "https://github.com/PostTrainLLM/posttrainllm/releases/download/mac-v0.1.0/posttrainllm-0.1.0-macOS.dmg",
      sha256: "67d7e476eb2abb9863fd902d5e76a65c1db2243f41e19004f436bb78ca157fb8",
    });
  });

  it("keeps an unverified candidate pending without exposing an artifact", () => {
    expect(
      evaluateMacRelease({
        ...macReleaseRecord,
        state: "pending-notarization",
        artifactURL: null,
        sha256: null,
        verification: {
          ...macReleaseRecord.verification,
          notarized: false,
          stapled: false,
          gatekeeperAccepted: false,
          checksumVerified: false,
        },
      }),
    ).toMatchObject({
      version: "0.1.0",
      build: "1",
      state: "pending-notarization",
      downloadable: false,
      artifactURL: null,
      sha256: null,
    });
  });

  it.each([
    ["missing record", undefined],
    ["missing version", { ...eligibleRelease(), version: "" }],
    ["missing build", { ...eligibleRelease(), build: "" }],
    [
      "malformed macOS version",
      { ...eligibleRelease(), minimumMacOS: "Sonoma" },
    ],
    ["missing record date", { ...eligibleRelease(), recordUpdated: "" }],
    [
      "malformed record date",
      { ...eligibleRelease(), recordUpdated: "2026-99-99" },
    ],
    ["malformed checksum", { ...eligibleRelease(), sha256: "abc123" }],
    [
      "non-HTTPS URL",
      {
        ...eligibleRelease(),
        artifactURL:
          "http://github.com/PostTrainLLM/posttrainllm/releases/download/v0.1.0/app.dmg",
      },
    ],
    [
      "unapproved host",
      {
        ...eligibleRelease(),
        artifactURL: "https://downloads.example.com/PostTrainLLM.dmg",
      },
    ],
    [
      "unapproved repository",
      {
        ...eligibleRelease(),
        artifactURL:
          "https://github.com/PostTrainLLM/other/releases/download/v0.1.0/app.dmg",
      },
    ],
    [
      "non-DMG artifact",
      {
        ...eligibleRelease(),
        artifactURL:
          "https://github.com/PostTrainLLM/posttrainllm/releases/download/v0.1.0/app.zip",
      },
    ],
  ])("fails closed for %s", (_name, candidate) => {
    const result = evaluateMacRelease(candidate);
    expect(result.downloadable).toBe(false);
    expect(result.artifactURL).toBeNull();
    expect(result.sha256).toBeNull();
  });

  it.each([
    "developerIdSigned",
    "hardenedRuntime",
    "notarized",
    "stapled",
    "gatekeeperAccepted",
    "checksumVerified",
  ] as const)("fails closed when %s is false", (gate) => {
    const candidate = eligibleRelease();
    candidate.verification[gate] = false;
    expect(evaluateMacRelease(candidate)).toMatchObject({
      downloadable: false,
      artifactURL: null,
      sha256: null,
    });
  });

  it("allows the reviewed GitHub Release only after every gate passes", () => {
    expect(evaluateMacRelease(eligibleRelease())).toMatchObject({
      state: "available",
      downloadable: true,
      artifactURL:
        "https://github.com/PostTrainLLM/posttrainllm/releases/download/v0.1.0/PostTrainLLM-0.1.0.dmg",
      sha256: "a".repeat(64),
    });
  });
});
