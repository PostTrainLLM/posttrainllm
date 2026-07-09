import { onLCP, onCLS, onINP, onTTFB, onFCP } from "web-vitals";

interface VitalMetric {
  name: string;
  value: number;
  rating: string;
  id: string;
  navigationType: string;
}

function sendToAnalytics(metric: VitalMetric) {
  // Send to PostHog if available, otherwise beacon to a fleet endpoint
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
    // Fallback: beacon to fleet analytics endpoint
    const body = JSON.stringify({
      project: import.meta.env.VITE_PROJECT_SLUG ?? "posttrainllm",
      ...metric,
    });
    navigator.sendBeacon("https://vitals.fleet.workers.dev/collect", body);
  }
}

export function initVitals() {
  onLCP(sendToAnalytics);
  onCLS(sendToAnalytics);
  onINP(sendToAnalytics);
  onTTFB(sendToAnalytics);
  onFCP(sendToAnalytics);
}
