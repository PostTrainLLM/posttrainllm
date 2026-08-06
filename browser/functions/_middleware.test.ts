import { describe, expect, it, vi } from "vitest";

import { onRequest } from "./_middleware";

describe("Pages HTML middleware", () => {
  it("prevents release HTML from surviving a deployment", async () => {
    const next = vi.fn(async () =>
      new Response("<!doctype html>", {
        headers: {
          "content-type": "text/html; charset=utf-8",
          "cache-control": "public, s-maxage=86400",
        },
      }),
    );

    const response = await onRequest({
      request: new Request("https://posttrainllm.com/"),
      next,
    } as never);

    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.text()).toBe("<!doctype html>");
  });

  it("leaves hashed assets on the normal Pages cache path", async () => {
    const next = vi.fn(async () =>
      new Response("asset", { headers: { "cache-control": "public, immutable" } }),
    );

    const response = await onRequest({
      request: new Request("https://posttrainllm.com/_astro/app.hash.js"),
      next,
    } as never);

    expect(response.headers.get("cache-control")).toBe("public, immutable");
  });
});
