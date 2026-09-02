import type { MacReleaseRecord } from "../data/mac-release";

const SHA256_PATTERN = /^[a-f\d]{64}$/i;
const VERSION_PATTERN = /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/;
const BUILD_PATTERN = /^\d+$/;
const MACOS_PATTERN = /^\d+(?:\.\d+){0,2}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const APPROVED_RELEASE_OWNER = "PostTrainLLM";
const APPROVED_RELEASE_REPOSITORY = "posttrainllm";

export interface PublicMacRelease {
  product: string;
  platform: string;
  architecture: string;
  version: string;
  build: string;
  minimumMacOS: string;
  recordUpdated: string;
  state: "pending-notarization" | "available";
  downloadable: boolean;
  artifactURL: string | null;
  sha256: string | null;
  verification: {
    developerIdSigned: boolean;
    hardenedRuntime: boolean;
    notarized: boolean;
    stapled: boolean;
    gatekeeperAccepted: boolean;
    checksumVerified: boolean;
  };
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isApprovedArtifactURL(value: unknown): value is string {
  if (!isNonEmptyString(value)) return false;

  try {
    const url = new URL(value);
    const expectedPrefix = `/${APPROVED_RELEASE_OWNER}/${APPROVED_RELEASE_REPOSITORY}/releases/download/`;
    return (
      url.protocol === "https:" &&
      url.hostname === "github.com" &&
      url.username === "" &&
      url.password === "" &&
      url.port === "" &&
      url.search === "" &&
      url.hash === "" &&
      url.pathname.startsWith(expectedPrefix) &&
      url.pathname.toLowerCase().endsWith(".dmg")
    );
  } catch {
    return false;
  }
}

export function evaluateMacRelease(input: unknown): PublicMacRelease {
  const source =
    input && typeof input === "object"
      ? (input as Partial<MacReleaseRecord>)
      : {};
  const verification =
    source.verification && typeof source.verification === "object"
      ? source.verification
      : ({} as Partial<MacReleaseRecord["verification"]>);

  const factualRecordValid =
    source.product === "PostTrainLLM" &&
    source.platform === "macOS" &&
    source.architecture === "Apple Silicon" &&
    isNonEmptyString(source.version) &&
    VERSION_PATTERN.test(source.version) &&
    isNonEmptyString(source.build) &&
    BUILD_PATTERN.test(source.build) &&
    isNonEmptyString(source.minimumMacOS) &&
    MACOS_PATTERN.test(source.minimumMacOS) &&
    isNonEmptyString(source.recordUpdated) &&
    ISO_DATE_PATTERN.test(source.recordUpdated) &&
    !Number.isNaN(Date.parse(`${source.recordUpdated}T00:00:00Z`));
  const verificationComplete =
    verification.developerIdSigned === true &&
    verification.hardenedRuntime === true &&
    verification.notarized === true &&
    verification.stapled === true &&
    verification.gatekeeperAccepted === true &&
    verification.checksumVerified === true;
  const downloadable =
    factualRecordValid &&
    source.state === "available" &&
    isApprovedArtifactURL(source.artifactURL) &&
    isNonEmptyString(source.sha256) &&
    SHA256_PATTERN.test(source.sha256) &&
    verificationComplete;

  return {
    product: isNonEmptyString(source.product) ? source.product : "PostTrainLLM",
    platform: source.platform === "macOS" ? source.platform : "macOS",
    architecture:
      source.architecture === "Apple Silicon"
        ? source.architecture
        : "Apple Silicon",
    version: isNonEmptyString(source.version) ? source.version : "unknown",
    build: isNonEmptyString(source.build) ? source.build : "unknown",
    minimumMacOS: isNonEmptyString(source.minimumMacOS)
      ? source.minimumMacOS
      : "unknown",
    recordUpdated: isNonEmptyString(source.recordUpdated)
      ? source.recordUpdated
      : "unknown",
    state: downloadable ? "available" : "pending-notarization",
    downloadable,
    artifactURL: downloadable ? source.artifactURL! : null,
    sha256: downloadable ? source.sha256!.toLowerCase() : null,
    verification: {
      developerIdSigned: verification.developerIdSigned === true,
      hardenedRuntime: verification.hardenedRuntime === true,
      notarized: verification.notarized === true,
      stapled: verification.stapled === true,
      gatekeeperAccepted: verification.gatekeeperAccepted === true,
      checksumVerified: verification.checksumVerified === true,
    },
  };
}

export function macReleaseStatusLabel(release: PublicMacRelease): string {
  return release.downloadable ? "Verified and ready" : "Notarization pending";
}
