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
  version: "0.2.0",
  build: "2",
  minimumMacOS: "14.0",
  recordUpdated: "2026-09-26",
  state: "available",
  artifactURL:
    "https://github.com/PostTrainLLM/posttrainllm/releases/download/mac-v0.2.0/posttrainllm-0.2.0-macOS.dmg",
  sha256: "32dca8d4bbe1ad041a8820f4b969d78ce1962bda96eadc7dee16b2448daf7947",
  verification: {
    developerIdSigned: true,
    hardenedRuntime: true,
    notarized: true,
    stapled: true,
    gatekeeperAccepted: true,
    checksumVerified: true,
  },
} satisfies MacReleaseRecord;
