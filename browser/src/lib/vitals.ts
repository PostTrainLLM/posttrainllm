import { onLCP, onCLS, onINP, onTTFB, onFCP } from "web-vitals";

interface VitalMetric {
  name: string;
  value: number;
  rating: string;
  id: string;
  navigationType: string;
}

function sendToAnalytics(metric: VitalMetric) {
  // Send to PostHog if available, otherwise use an explicitly configured
  // endpoint. A public static build must not emit failing cross-origin beacons.
  const posthog = (window as any).posthog;
  if (posthog && typeof posthog.capture === "function") {
    posthog.capture("web_vital", {
      name: metric.name,
      value: Math.round(metric.value),
      rating: metric.rating,
      id: metric.id,
      navigation_type: metric.navigationType,
    });
  } else {
    const endpoint = import.meta.env.VITE_WEB_VITALS_ENDPOINT?.trim();
    if (!endpoint) return;
    const body = JSON.stringify({
      project: import.meta.env.VITE_PROJECT_SLUG ?? "posttrainllm",
      ...metric,
    });
    navigator.sendBeacon(endpoint, body);
  }
}

export function initVitals() {
  onLCP(sendToAnalytics);
  onCLS(sendToAnalytics);
  onINP(sendToAnalytics);
  onTTFB(sendToAnalytics);
  onFCP(sendToAnalytics);
}
