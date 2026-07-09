/**
 * Client-side API call timing via the Resource Timing API.
 *
 * Polls `performance.getEntriesByType('resource')` for fetch/XHR entries,
 * groups them by normalized route, and emits `api_call_timing` events to
 * PostHog with p50/p90/max duration + TTFB. This captures the full
 * round-trip latency the user experiences (network + server), which the
 * backend `withTiming()` / `Server-Timing` header cannot measure.
 *
 * No call-site changes needed — the browser records this automatically.
 * Limitation: Resource Timing does not expose HTTP status codes for
 * fetch/XHR, so latency-by-status is not available here.
 *
 * Usage:
 *   import { initApiTiming } from '@/lib/api-timing';
 *   initApiTiming();  // call once after PostHog is initialized
 */

interface ApiTimingSample {
  route: string;
  durationMs: number;
  ttfbMs: number;
  transferSize: number;
}

// Configurable via initApiTiming() options.
let _extraPatterns: RegExp[] = [];
let _intervalMs = 30_000;
let _flushTimer: ReturnType<typeof setInterval> | null = null;
let _lastSeenStart = 0;
let _projectSlug = 'posttrainllm';

/** True for fetch() and XMLHttpRequest calls only (not scripts, images, etc.). */
function isApiCall(entry: PerformanceResourceTiming): boolean {
  return entry.initiatorType === 'fetch' || entry.initiatorType === 'xmlhttprequest';
}

/** Match same-origin /api/ paths OR any configured extra patterns. */
function matchesPatterns(url: string): boolean {
  try {
    const u = new URL(url, window.location.origin);
    // Same-origin /api/ — always include.
    if (u.origin === window.location.origin && u.pathname.startsWith('/api/')) return true;
    // Extra patterns (e.g. cross-origin API hosts).
    return _extraPatterns.some((p) => p.test(url));
  } catch {
    return false;
  }
}

/**
 * Collapse dynamic path segments so /api/articles/123 → /api/articles/:id.
 * Keeps cardinality low for PostHog grouping.
 */
function normalizeRoute(url: string): string {
  try {
    const u = new URL(url, window.location.origin);
    const segments = u.pathname.split('/').map((seg) => {
      if (/^\d+$/.test(seg)) return ':id';
      if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(seg)) return ':id';
      if (/^[a-zA-Z0-9_-]{20,}$/.test(seg)) return ':id';
      return seg;
    });
    // Include host for cross-origin calls, omit for same-origin.
    const prefix = u.origin === window.location.origin ? '' : `${u.host}`;
    return `${prefix}${segments.join('/')}`;
  } catch {
    return url;
  }
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.min(Math.floor(sorted.length * p), sorted.length - 1);
  return sorted[idx]!;
}

function collectAndFlush(): void {
  const entries = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
  if (entries.length === 0) return;

  const samples: ApiTimingSample[] = [];
  let maxStart = _lastSeenStart;

  for (const entry of entries) {
    if (entry.startTime <= _lastSeenStart) continue;
    if (entry.startTime > maxStart) maxStart = entry.startTime;
    if (!isApiCall(entry) || !matchesPatterns(entry.name)) continue;

    samples.push({
      route: normalizeRoute(entry.name),
      durationMs: Math.round(entry.duration),
      ttfbMs: Math.round(entry.responseStart - entry.startTime),
      transferSize: entry.transferSize,
    });
  }

  _lastSeenStart = maxStart;

  if (samples.length === 0) return;

  const posthog = (
    window as unknown as { posthog?: { capture: (e: string, p: Record<string, unknown>) => void } }
  ).posthog;
  if (!posthog?.capture) return;

  // Group by route → aggregate stats.
  const byRoute = new Map<string, ApiTimingSample[]>();
  for (const s of samples) {
    const group = byRoute.get(s.route) ?? [];
    group.push(s);
    byRoute.set(s.route, group);
  }

  for (const [route, group] of byRoute) {
    const durations = group.map((s) => s.durationMs).sort((a, b) => a - b);
    const ttfbs = group.map((s) => s.ttfbMs).sort((a, b) => a - b);

    posthog.capture('api_call_timing', {
      project_id: _projectSlug,
      route,
      sample_count: group.length,
      duration_p50: percentile(durations, 0.5),
      duration_p90: percentile(durations, 0.9),
      duration_max: durations[durations.length - 1] ?? 0,
      ttfb_p50: percentile(ttfbs, 0.5),
      ttfb_p90: percentile(ttfbs, 0.9),
      transfer_size_total: group.reduce((sum, s) => sum + s.transferSize, 0),
    });
  }
}

export interface ApiTimingOptions {
  /** Additional URL patterns to treat as API calls (beyond same-origin /api/). */
  urlPatterns?: RegExp[];
  /** Sampling interval in milliseconds. Default: 30000 (30s). */
  intervalMs?: number;
  /** Project slug for PostHog grouping. */
  projectSlug?: string;
}

/**
 * Start sampling API call timings. Call once after PostHog is initialized.
 * Safe to call in SSR — no-ops if `window` is undefined.
 */
export function initApiTiming(options?: ApiTimingOptions): void {
  if (typeof window === 'undefined') return;

  if (options?.urlPatterns) _extraPatterns = options.urlPatterns;
  if (options?.intervalMs) _intervalMs = options.intervalMs;
  if (options?.projectSlug) _projectSlug = options.projectSlug;

  if (_flushTimer) clearInterval(_flushTimer);
  _flushTimer = setInterval(collectAndFlush, _intervalMs);

  // Best-effort flush when the page is hidden or unloaded.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') collectAndFlush();
  });
}

/** Stop sampling and flush remaining entries. */
export function stopApiTiming(): void {
  if (_flushTimer) {
    clearInterval(_flushTimer);
    _flushTimer = null;
  }
  collectAndFlush();
}
