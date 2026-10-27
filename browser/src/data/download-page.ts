import { macReleaseRecord } from "./mac-release";
import { evaluateMacRelease, macReleaseStatusLabel } from "../lib/mac-release";
export const release = evaluateMacRelease(macReleaseRecord);
export const statusLabel = macReleaseStatusLabel(release);
export const completedChecks = Object.values(release.verification).filter(
  Boolean,
).length;
export const recordUpdated =
  release.recordUpdated === "unknown"
    ? "Unknown"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeZone: "UTC",
      }).format(new Date(`${release.recordUpdated}T00:00:00Z`));
export const checks = [
  {
    label: "Developer ID signature",
    detail: "Personal distribution identity",
    complete: release.verification.developerIdSigned,
  },
  {
    label: "Hardened runtime",
    detail: "Runtime protection enabled",
    complete: release.verification.hardenedRuntime,
  },
  {
    label: "Apple notarization",
    detail: "Apple trust service",
    complete: release.verification.notarized,
  },
  {
    label: "Stapled ticket",
    detail: "Offline trust receipt",
    complete: release.verification.stapled,
  },
  {
    label: "Gatekeeper assessment",
    detail: "Clean-machine launch policy",
    complete: release.verification.gatekeeperAccepted,
  },
  {
    label: "Artifact checksum",
    detail: "Published DMG integrity",
    complete: release.verification.checksumVerified,
  },
] as const;

export const releaseSummary = release.downloadable
  ? "PostTrainLLM packages the local specialist factory into a native Apple Silicon app. Notarization, stapling, Gatekeeper, and the published checksum all agree on this exact DMG, so the download is open."
  : "PostTrainLLM packages the local specialist factory into a native Apple Silicon app. The current candidate is not downloadable yet: the site stays closed until notarization, stapling, Gatekeeper, and checksum verification all agree on the exact DMG.";
