type MacReleaseState = "pending-notarization" | "available";

interface MacReleaseVerification {
  developerIdSigned: boolean;
  hardenedRuntime: boolean;
  notarized: boolean;
  stapled: boolean;
  gatekeeperAccepted: boolean;
  checksumVerified: boolean;
}

export interface MacReleaseRecord {
  product: string;
  platform: "macOS";
  architecture: "Apple Silicon";
  version: string;
  build: string;
  minimumMacOS: string;
  recordUpdated: string;
  state: MacReleaseState;
  artifactURL: string | null;
  sha256: string | null;
  verification: MacReleaseVerification;
}

export const macReleaseRecord = {
  product: "PostTrainLLM",
  platform: "macOS",
  architecture: "Apple Silicon",
  version: "0.1.0",
  build: "1",
  minimumMacOS: "14.0",
  recordUpdated: "2026-09-06",
  state: "available",
  artifactURL:
    "https://github.com/PostTrainLLM/posttrainllm/releases/download/mac-v0.1.0/posttrainllm-0.1.0-macOS.dmg",
  sha256: "67d7e476eb2abb9863fd902d5e76a65c1db2243f41e19004f436bb78ca157fb8",
  verification: {
    developerIdSigned: true,
    hardenedRuntime: true,
    notarized: true,
    stapled: true,
    gatekeeperAccepted: true,
    checksumVerified: true,
  },
} satisfies MacReleaseRecord;
