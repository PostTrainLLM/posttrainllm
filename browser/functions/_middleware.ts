// CF Pages Functions middleware keeps release HTML fresh. Hashed assets are
// still cached by Pages/public headers, but document responses must not remain
// pinned to an older deployment.

interface Env {
  ASSETS?: { fetch: (req: Request) => Promise<Response> };
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request } = context;

  if (request.method !== "GET") {
    return context.next();
  }

  const url = new URL(request.url);
  // Only cache HTML routes. Skip assets, API, etc.
  if (
    url.pathname.startsWith("/_astro/") ||
    url.pathname.startsWith("/_next/") ||
    url.pathname.startsWith("/api/") ||
    url.pathname.includes(".")
  ) {
    // Asset paths — let Pages handle directly (already cached).
    return context.next();
  }

  const response = await context.next();
  const contentType = response.headers.get("content-type") ?? "";
  if (response.status !== 200 || !contentType.includes("text/html")) {
    return response;
  }

  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};
