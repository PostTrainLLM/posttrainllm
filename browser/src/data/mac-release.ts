export type MacReleaseState = "pending-notarization" | "available";

export interface MacReleaseVerification {
  developerIdSigned: boolean;
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
  recordUpdated: "2026-08-12",
  state: "pending-notarization",
  artifactURL: null,
  sha256: null,
  verification: {
    developerIdSigned: true,
    notarized: false,
    stapled: false,
    gatekeeperAccepted: false,
    checksumVerified: false,
  },
} satisfies MacReleaseRecord;
