// Build-only content projection. The finalizer consumes and removes this file
// before deployment; it is never part of the public route registry.
import { publicMarkdownSources } from "../data/public-markdown-sources";
export function GET() {
  return new Response(JSON.stringify(publicMarkdownSources), {
    headers: { "Content-Type": "application/json", "X-Robots-Tag": "noindex" },
  });
}
