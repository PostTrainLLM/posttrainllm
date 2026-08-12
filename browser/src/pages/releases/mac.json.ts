import type { APIRoute } from "astro";
import { macReleaseRecord } from "../../data/mac-release";
import { evaluateMacRelease } from "../../lib/mac-release";

export const prerender = true;

export const GET: APIRoute = () =>
  new Response(`${JSON.stringify(evaluateMacRelease(macReleaseRecord), null, 2)}\n`, {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300",
    },
  });
