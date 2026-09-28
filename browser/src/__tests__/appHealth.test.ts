import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";

const layout = await readFile(
  new URL("../layouts/Default.astro", import.meta.url),
  "utf8",
);
const landingPage = await readFile(
  new URL("../pages/index.astro", import.meta.url),
  "utf8",
);
const browserLogger = await readFile(
  new URL("../../public/app-health-log.js", import.meta.url),
  "utf8",
);

describe("App Health browser analytics", () => {
  it("loads the origin-bound tracker once behind the telemetry flag", () => {
    expect(layout.match(/health\.sassmaker\.com\/tracker\.js/g)).toHaveLength(
      1,
    );
    expect(layout).toContain(
      'data-key="ahk_pub_dbdf16dbbb0bf141edf166fb7a314d45760bb0cd061d3d8e0e30c70de1e620e6"',
    );
    expect(layout).toContain(
      'data-project="app-87fd048a-cbd2-4110-9609-be67389fd239"',
    );
    expect(layout).toContain(
      'data-endpoint="https://ingest.sassmaker.com/v1/browser"',
    );
  });

  it("logs the homepage quickstart CTA through the shared browser logger", () => {
    expect(landingPage.match(/data-log="quickstart_opened"/g)).toHaveLength(5);
    expect(landingPage.match(/data-log="specialist_proof_opened"/g)).toHaveLength(
      1,
    );
    expect(browserLogger).toContain('closest("[data-log]")');
    expect(browserLogger).toContain("send(name, {");
    expect(browserLogger).toContain("window.appHealth.track(name)");
  });
});
