// CF Pages Functions middleware:
// - Keeps release HTML fresh (hashed assets still cached by Pages headers).
// - Handles Accept: text/markdown negotiation for pages with .md alternates.
// - Returns agent-friendly markdown 404s for unknown paths.
// - Serves /openapi.json with the public API spec.

interface Env {
  ASSETS?: { fetch: (req: Request) => Promise<Response> };
}

const OPENAPI_SPEC = {
  openapi: "3.1.0",
  info: {
    title: "PostTrainLLM public API",
    version: "1.1.0",
    description:
      "PostTrainLLM is a Mac-local LLM specialist factory. The public web API exposes read-only agent surfaces: the agent catalog, sitemap, llms.txt, and per-page markdown alternates. Training, evaluation, and packaging run locally and do not expose a remote API.",
    contact: { name: "PostTrainLLM", url: "https://posttrainllm.com" },
    license: {
      name: "MIT",
      url: "https://github.com/PostTrainLLM/posttrainllm/blob/main/LICENSE",
    },
  },
  servers: [{ url: "https://posttrainllm.com" }],
  tags: [
    { name: "agent-surfaces", description: "Machine-readable public surfaces" },
  ],
  paths: {
    "/api/ai": {
      get: {
        operationId: "getAgentCatalog",
        tags: ["agent-surfaces"],
        summary: "Agent catalog",
        description:
          "JSON inventory of public agent surfaces: llms.txt, llms-full.txt, sitemap, robots, and per-page markdown alternates.",
        responses: {
          "200": {
            description: "Agent catalog",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/AgentCatalog" },
              },
            },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
    "/llms.txt": {
      get: {
        operationId: "getLlmsTxt",
        tags: ["agent-surfaces"],
        summary: "llms.txt index",
        description: "Compact agent index following the llms.txt convention.",
        responses: {
          "200": {
            description: "Markdown index",
            content: { "text/plain": { schema: { type: "string" } } },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
    "/llms-full.txt": {
      get: {
        operationId: "getLlmsFullTxt",
        tags: ["agent-surfaces"],
        summary: "Full agent brief",
        description:
          "Full canonical agent brief with product, architecture, and surface inventory.",
        responses: {
          "200": {
            description: "Markdown brief",
            content: { "text/plain": { schema: { type: "string" } } },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
    "/sitemap.xml": {
      get: {
        operationId: "getSitemap",
        tags: ["agent-surfaces"],
        summary: "Sitemap",
        description: "XML sitemap listing all public HTML routes.",
        responses: {
          "200": {
            description: "XML sitemap",
            content: { "application/xml": { schema: { type: "string" } } },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
    "/openapi.json": {
      get: {
        operationId: "getOpenApiSpec",
        tags: ["agent-surfaces"],
        summary: "OpenAPI specification",
        description: "This document.",
        responses: {
          "200": {
            description: "OpenAPI 3.1 spec",
            content: { "application/json": { schema: { type: "object" } } },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
    "/releases/mac.json": {
      get: {
        operationId: "getMacRelease",
        tags: ["agent-surfaces"],
        summary: "Verified Mac release record",
        description:
          "Fail-closed release metadata. A Mac artifact is downloadable only when Developer ID signing, hardened runtime, notarization, stapling, Gatekeeper assessment, a GitHub DMG URL, and SHA-256 evidence are all present.",
        responses: {
          "200": {
            description: "Native Mac release state",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/MacRelease" },
              },
            },
          },
          "404": {
            description: "Error response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Error" },
              },
            },
          },
        },
      },
    },
  },
  components: {
    schemas: {
      AgentCatalog: {
        type: "object",
        properties: {
          name: { type: "string" },
          version: { type: "string" },
          url: { type: "string", format: "uri" },
          llms: { type: "string", format: "uri" },
          llmsFull: { type: "string", format: "uri" },
          sitemap: { type: "string", format: "uri" },
          robots: { type: "string", format: "uri" },
          openapi: { type: "string", format: "uri" },
          release: { type: "string", format: "uri" },
          markdown: {
            type: "object",
            properties: {
              suffix: { type: "string" },
              negotiation: { type: "boolean" },
            },
          },
          surfaces: {
            type: "array",
            items: {
              type: "object",
              properties: {
                id: { type: "string" },
                url: { type: "string", format: "uri" },
                md: { type: "string", format: "uri" },
                kind: { type: "string" },
                title: { type: "string" },
                description: { type: "string" },
              },
            },
          },
          capabilities: {
            type: "object",
            additionalProperties: {
              type: "array",
              items: { $ref: "#/components/schemas/Capability" },
            },
          },
          experimentSummary: {
            $ref: "#/components/schemas/ExperimentSummary",
          },
          learningSummary: {
            $ref: "#/components/schemas/LearningSummary",
          },
        },
      },
      Capability: {
        type: "object",
        properties: {
          name: { type: "string" },
          url: { type: "string", format: "uri" },
        },
        required: ["name", "url"],
      },
      ExperimentSummary: {
        type: "object",
        properties: {
          total: { type: "integer" },
          resolved: { type: "integer" },
          worked: { type: "integer" },
          workedWithCaveat: { type: "integer" },
          nonPositiveOrMixed: { type: "integer" },
          byStatus: {
            type: "object",
            additionalProperties: { type: "integer" },
          },
          interpretation: { type: "string" },
        },
      },
      LearningSummary: {
        type: "object",
        properties: {
          paths: { type: "integer" },
          recipes: { type: "integer" },
          stages: { type: "integer" },
          buildableArtifacts: { type: "integer" },
        },
      },
      MacRelease: {
        type: "object",
        properties: {
          version: { type: "string" },
          build: { type: "string" },
          state: { type: "string" },
          downloadable: { type: "boolean" },
          artifactURL: { type: ["string", "null"], format: "uri" },
          sha256: { type: ["string", "null"] },
          verification: {
            $ref: "#/components/schemas/MacReleaseVerification",
          },
        },
      },
      MacReleaseVerification: {
        type: "object",
        properties: {
          developerIdSigned: { type: "boolean" },
          hardenedRuntime: { type: "boolean" },
          notarized: { type: "boolean" },
          stapled: { type: "boolean" },
          gatekeeperAccepted: { type: "boolean" },
          checksumVerified: { type: "boolean" },
        },
      },
      Error: {
        type: "object",
        properties: {
          error: {
            type: "object",
            properties: {
              code: { type: "string" },
              message: { type: "string" },
              path: { type: "string" },
            },
            required: ["code", "message", "path"],
          },
        },
        required: ["error"],
      },
    },
  },
};

function wantsMarkdown(request: Request): boolean {
  const accept = (request.headers.get("accept") || "").toLowerCase();
  if (!accept.includes("text/markdown")) return false;
  if (!accept.includes("text/html")) return true;
  return accept.indexOf("text/markdown") < accept.indexOf("text/html");
}

function normalizePath(pathname: string): string {
  if (!pathname || pathname === "/") return "/";
  const withSlash = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return withSlash.replace(/\/{2,}/g, "/").replace(/\/+$/, "") || "/";
}

function markdownPathFor(pathname: string): string {
  const path = normalizePath(pathname);
  return path === "/" ? "/index.md" : `${path}.md`;
}

function markdown404(pathname: string, method: string): Response {
  const path = normalizePath(pathname);
  const body = `# 404 — Not Found

\`${path}\` does not exist on posttrainllm.com.

## Where to look next

- [Home](https://posttrainllm.com/)
- [Sitemap](https://posttrainllm.com/sitemap.xml)
- [Agent index](https://posttrainllm.com/llms.txt)
- [Full agent brief](https://posttrainllm.com/llms-full.txt)
- [Agent catalog (JSON)](https://posttrainllm.com/api/ai)
- [Documentation](https://posttrainllm.com/docs/)
`;
  return new Response(method === "HEAD" ? null : body, {
    status: 404,
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function jsonError(
  status: number,
  code: string,
  message: string,
  path: string,
): Response {
  return new Response(
    JSON.stringify({
      error: {
        code,
        message,
        path,
        documentation: "https://posttrainllm.com/docs/",
      },
    }),
    {
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "access-control-allow-origin": "*",
        "RateLimit-Limit": "120",
        "RateLimit-Remaining": "119",
        "RateLimit-Reset": "60",
      },
    },
  );
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request } = context;

  if (request.method !== "GET" && request.method !== "HEAD") {
    return context.next();
  }

  const url = new URL(request.url);
  const pathname = url.pathname;

  // /openapi.json — serve the spec directly.
  if (pathname === "/openapi.json" || pathname === "/openapi.yaml") {
    return new Response(JSON.stringify(OPENAPI_SPEC, null, 2), {
      headers: {
        "content-type": "application/json; charset=utf-8",
        "access-control-allow-origin": "*",
        "cache-control":
          "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
        "RateLimit-Limit": "120",
        "RateLimit-Remaining": "119",
        "RateLimit-Reset": "60",
      },
    });
  }

  // JSON errors for unknown /api/* paths.
  if (pathname.startsWith("/api/") && pathname !== "/api/ai") {
    return jsonError(
      404,
      "not_found",
      `Unknown API path: ${pathname}`,
      pathname,
    );
  }

  // Skip asset paths — let Pages handle directly.
  if (
    pathname.startsWith("/_astro/") ||
    pathname.startsWith("/_next/") ||
    (pathname.includes(".") && !pathname.endsWith(".md"))
  ) {
    return context.next();
  }

  // Accept: text/markdown negotiation for HTML pages that have a .md alternate.
  if (
    wantsMarkdown(request) &&
    !pathname.endsWith(".md") &&
    !pathname.startsWith("/api/")
  ) {
    const mdPath = markdownPathFor(pathname);
    // Probe the .md alternate via the assets binding.
    if (context.env.ASSETS) {
      const mdUrl = new URL(url);
      mdUrl.pathname = mdPath;
      const mdResponse = await context.env.ASSETS.fetch(
        new Request(mdUrl.toString(), request),
      );
      if (mdResponse.status === 200) {
        const headers = new Headers(mdResponse.headers);
        headers.set("content-type", "text/markdown; charset=utf-8");
        headers.set("vary", "Accept, Accept-Encoding");
        headers.set("x-content-type-options", "nosniff");
        return new Response(
          request.method === "HEAD" ? null : mdResponse.body,
          {
            status: 200,
            headers,
          },
        );
      }
    }
  }

  const response = await context.next();
  const contentType = response.headers.get("content-type") ?? "";

  // Agent-friendly 404 with markdown recovery body.
  if (response.status === 404 && !pathname.startsWith("/api/")) {
    if (wantsMarkdown(request)) {
      return markdown404(pathname, request.method);
    }
    const headers = new Headers(response.headers);
    headers.set("vary", "Accept, Accept-Encoding");
    return new Response(response.body, { status: 404, headers });
  }

  // Add rate-limit headers to /api/ai responses.
  if (pathname === "/api/ai" && response.status === 200) {
    const headers = new Headers(response.headers);
    headers.set("RateLimit-Limit", "120");
    headers.set("RateLimit-Remaining", "119");
    headers.set("RateLimit-Reset", "60");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  }

  if (response.status !== 200 || !contentType.includes("text/html")) {
    return response;
  }

  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  // Add Vary: Accept to HTML pages that might have markdown alternates.
  const existingVary = headers.get("vary");
  headers.set(
    "vary",
    existingVary ? `${existingVary}, Accept` : "Accept, Accept-Encoding",
  );
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};
