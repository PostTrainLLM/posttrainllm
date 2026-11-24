import { afterEach, describe, expect, it, vi } from "vitest";
import { setupBrowserTerminal } from "../specialists/browser-terminal";

function setup() {
  let finishRead!: (text: string) => void;
  const fileRead = new Promise<string>((resolve) => {
    finishRead = resolve;
  });
  const worker = { postMessage: vi.fn(), terminate: vi.fn() };
  vi.stubGlobal(
    "Worker",
    class {
      postMessage = worker.postMessage;
      terminate = worker.terminate;
    },
  );
  vi.stubGlobal("window", new EventTarget());
  vi.stubGlobal("document", new EventTarget());
  const load = new EventTarget();
  const controls = {
    "#sp-terminal-provider": Object.assign(new EventTarget(), {
      value: "wasm",
    }),
    "#sp-terminal-artifact": Object.assign(new EventTarget(), {
      files: [{ size: 4, text: () => fileRead }],
    }),
    "#sp-terminal-stop": new EventTarget(),
    "#sp-terminal-load": load,
  };
  const root = {
    querySelector: (selector: keyof typeof controls) => controls[selector],
  } as unknown as HTMLElement;
  const changed = vi.fn();
  const status = vi.fn();
  const terminal = setupBrowserTerminal(root, changed, status);
  return { changed, status, terminal, load, finishRead, worker };
}

afterEach(() => vi.unstubAllGlobals());

describe("terminal worker lifecycle", () => {
  it("tears down a pending file read before an Astro page swap", async () => {
    const { terminal, worker, load, finishRead } = setup();
    load.dispatchEvent(new Event("click"));
    document.dispatchEvent(new Event("astro:before-swap"));
    finishRead("{}");
    await Promise.resolve();
    expect(worker.terminate).toHaveBeenCalledOnce();
    expect(worker.postMessage).not.toHaveBeenCalled();
    expect(terminal.ready()).toBe(false);
  });

  it("leaves the active workflow alone on pagehide when no terminal worker exists", () => {
    const { changed, status } = setup();
    window.dispatchEvent(new Event("pagehide"));
    expect(changed).not.toHaveBeenCalled();
    expect(status).not.toHaveBeenCalled();
  });
});
