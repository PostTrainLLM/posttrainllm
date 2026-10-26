import { afterEach, expect, it, vi } from "vitest";
import { setupBrowserDecision } from "../specialists/browser-decision";

function fixture() {
  const controls = new Map<
    string,
    EventTarget & { value: string; disabled: boolean; files?: unknown }
  >();
  for (const name of ["provider", "files", "example", "load", "stop"])
    controls.set(
      name,
      Object.assign(new EventTarget(), { value: "wasm", disabled: false }),
    );
  controls.get("files")!.files = [
    "manifest.json",
    "model.onnx",
    "model.onnx.data",
    "tokenizer.json",
    "tokenizer_config.json",
  ].map((name) => ({
    name,
    size: 1,
    text: async () => "{}",
    arrayBuffer: async () => new ArrayBuffer(1),
  }));
  const workers: {
    onmessage?: (event: { data: unknown }) => void;
    last: { id: number };
    terminate: ReturnType<typeof vi.fn>;
    postMessage: ReturnType<typeof vi.fn>;
  }[] = [];
  class Worker {
    last = { id: 0 };
    terminate = vi.fn();
    postMessage = vi.fn((message: { id: number }) => {
      this.last = message;
    });
    constructor() {
      workers.push(this);
    }
  }
  vi.stubGlobal("Worker", Worker);
  vi.stubGlobal("window", new EventTarget());
  vi.stubGlobal("document", new EventTarget());
  const status = vi.fn();
  const controller = setupBrowserDecision(
    {
      querySelector: (selector: string) =>
        controls.get(selector.replace("#sp-decision-", "")),
    } as unknown as HTMLElement,
    vi.fn(),
    status,
    vi.fn(),
  );
  const click = (name: string) =>
    controls.get(name)!.dispatchEvent(new Event("click"));
  const reply = (index = 0) => {
    const worker = workers[index];
    worker.onmessage?.({
      data: { id: worker.last.id, result: { example: {}, max_tokens: 256 } },
    });
  };
  return { controller, controls, workers, status, click, reply };
}
const settle = async () => {
  for (let n = 0; n < 20; n++) await Promise.resolve();
};
afterEach(() => {
  document.dispatchEvent(new Event("astro:before-swap"));
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("Stop invalidates a pending prediction immediately and ignores its late reply", async () => {
  const f = fixture();
  f.click("load");
  await settle();
  f.reply();
  await settle();
  expect(f.controller.ready()).toBe(true);
  const pending = f.controller.execute({ item: {} });
  const rejected = expect(pending).rejects.toThrow(/stopped/);
  f.click("stop");
  f.reply();
  await rejected;
  await settle();
  expect(f.controller.ready()).toBe(false);
  expect(f.workers[0].terminate).toHaveBeenCalledOnce();
  expect(f.status.mock.lastCall?.[0]).toBe("Browser decision stopped.");
});

it("teardown invalidates an unfinished file read before worker creation", async () => {
  const f = fixture();
  let release!: (value: string) => void;
  const files = f.controls.get("files")!.files as {
    text: () => Promise<string>;
  }[];
  files[0].text = () =>
    new Promise((resolve) => {
      release = resolve;
    });
  f.click("load");
  await settle();
  document.dispatchEvent(new Event("astro:before-swap"));
  release("{}");
  await settle();
  expect(f.workers).toHaveLength(0);
  expect(f.controller.ready()).toBe(false);
});

it("timeouts terminate ownership and cannot activate a late load", async () => {
  vi.useFakeTimers();
  const f = fixture();
  f.click("load");
  await settle();
  await vi.advanceTimersByTimeAsync(45_000);
  f.reply();
  await settle();
  expect(f.controller.ready()).toBe(false);
  expect(f.workers[0].terminate).toHaveBeenCalledOnce();
  expect(f.status.mock.lastCall?.[0]).toContain("45-second budget");
  expect(vi.getTimerCount()).toBe(0);
});

it("a synchronous transfer failure clears the pending request for a retry", async () => {
  const f = fixture();
  f.click("load");
  await settle();
  f.reply();
  await settle();
  f.workers[0].postMessage.mockImplementationOnce(() => {
    throw Error("transfer failed");
  });
  await expect(f.controller.execute({})).rejects.toThrow("transfer failed");
  const next = f.controller.execute({});
  f.reply();
  await expect(next).resolves.toHaveProperty("max_tokens", 256);
});
