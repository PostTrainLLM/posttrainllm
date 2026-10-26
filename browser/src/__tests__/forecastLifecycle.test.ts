import { afterEach, describe, expect, it, vi } from "vitest";
import { setupBrowserForecast } from "../specialists/browser-forecast";

class Control extends EventTarget {
  value = "wasm";
  disabled = false;
  files = [
    {
      size: 1,
      arrayBuffer: async () => new ArrayBuffer(1),
      text: async () => "{}",
    },
  ];
  click() {
    this.dispatchEvent(new Event("click"));
  }
}
class StubWorker {
  static instances: StubWorker[] = [];
  onmessage?: (event: { data: unknown }) => void;
  onerror?: () => void;
  messages: { id: number }[] = [];
  terminate = vi.fn();
  constructor() {
    StubWorker.instances.push(this);
  }
  postMessage(message: { id: number }) {
    this.messages.push(message);
  }
  reply() {
    this.onmessage?.({
      data: {
        id: this.messages.at(-1)!.id,
        result: { example: {}, shape: { targets: 1, context: 8, horizon: 1 } },
      },
    });
  }
}
function setup() {
  const controls = Object.fromEntries(
    ["provider", "model", "manifest", "example", "stop", "load"].map((name) => [
      name,
      new Control(),
    ]),
  );
  vi.stubGlobal("Worker", StubWorker);
  vi.stubGlobal("window", new EventTarget());
  vi.stubGlobal("document", new EventTarget());
  const status = vi.fn();
  const controller = setupBrowserForecast(
    {
      querySelector: (selector: string) =>
        controls[selector.replace("#sp-forecast-", "")],
    } as unknown as HTMLElement,
    vi.fn(),
    status,
    vi.fn(),
  );
  return { controls, status, controller };
}
const flush = async () => {
  for (let i = 0; i < 5; i++) await Promise.resolve();
};
afterEach(() => {
  document.dispatchEvent(new Event("astro:before-swap"));
  vi.useRealTimers();
  vi.unstubAllGlobals();
  StubWorker.instances = [];
});
describe("forecast worker ownership", () => {
  it("rejects a late load reply after a provider change", async () => {
    const { controls, controller, status } = setup();
    controls.load.click();
    await flush();
    const worker = StubWorker.instances[0];
    controls.provider.value = "python";
    controls.provider.dispatchEvent(new Event("change"));
    const message = status.mock.lastCall?.[0];
    worker.reply();
    await flush();
    expect(worker.terminate).toHaveBeenCalledOnce();
    expect(controller.ready()).toBe(false);
    expect(status.mock.lastCall?.[0]).toBe(message);
    expect(controls.example.disabled).toBe(true);
  });
  it("terminates a timed-out request and prevents late activation", async () => {
    vi.useFakeTimers();
    const { controls, controller, status } = setup();
    controls.load.click();
    await flush();
    const worker = StubWorker.instances[0];
    await vi.advanceTimersByTimeAsync(45_000);
    worker.reply();
    await flush();
    expect(controller.ready()).toBe(false);
    expect(worker.terminate).toHaveBeenCalledOnce();
    expect(status.mock.lastCall?.[0]).toContain("45-second execution budget");
    expect(vi.getTimerCount()).toBe(0);
  });
  it("invalidates an asynchronous file read on teardown before creating a worker", async () => {
    const { controls, controller } = setup();
    let finish!: (value: ArrayBuffer) => void;
    controls.model.files[0].arrayBuffer = () =>
      new Promise((resolve) => {
        finish = resolve;
      });
    controls.load.click();
    await flush();
    document.dispatchEvent(new Event("astro:before-swap"));
    finish(new ArrayBuffer(1));
    await flush();
    expect(StubWorker.instances).toHaveLength(0);
    expect(controller.ready()).toBe(false);
  });
});

it("stops a new forecast worker on every pagehide after BFCache-style restore", async () => {
  const { controls, controller } = setup();
  for (let n = 0; n < 2; n++) {
    controls.load.click();
    await flush();
    const worker = StubWorker.instances[n];
    worker.reply();
    await flush();
    expect(controller.ready()).toBe(true);
    window.dispatchEvent(new Event("pagehide"));
    expect(worker.terminate).toHaveBeenCalledOnce();
    expect(controller.ready()).toBe(false);
    window.dispatchEvent(new Event("pageshow"));
  }
});
