"""Same-origin loopback bridge for the existing browser lab's specialist modes.

Serves only built public assets; model/data paths are operator-selected or
generated, never accepted as HTTP file paths. No CORS or shell execution.
Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import uuid
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import Budget, ROOT, read_json


class LabRuntime:
    def __init__(
        self,
        decision_model,
        decision_revision,
        forecast_model,
        forecast_revision,
        terminal_model,
        backend="mlx",
    ):
        self.decision_model = decision_model
        self.decision_revision = decision_revision
        self.forecast_model = forecast_model
        self.forecast_revision = forecast_revision
        self.terminal_model = terminal_model
        self.backend = backend
        self.lock = threading.Lock()
        self.decision = self.forecast = self.terminal = None
        self.sessions = {}
        self.artifacts = {}

    def destination(self, mode):
        key = uuid.uuid4().hex
        path = ROOT / "runs" / "specialist-labs" / "web" / key / mode
        self.artifacts[key] = (mode, path)
        return key, path

    def run(self, mode, action, payload):
        budget = Budget(60)
        if mode == "decision":
            result = self.run_decision(action, payload, budget)
        elif mode == "forecast":
            result = self.run_forecast(action, payload, budget)
        elif mode == "terminal":
            result = self.run_terminal(action, payload, budget)
        else:
            raise ValueError("unknown specialist mode")
        return {"result": result, "measurements": budget.measurements()}

    def run_decision(self, action, payload, budget):
        import decision

        if action in ("predict", "score"):
            if self.decision is None:
                self.decision = decision.DecisionModel(
                    self.decision_model,
                    self.backend,
                    self.decision_revision,
                    budget=budget,
                )
            self.decision.budget = budget
            rows = payload.get("rows", [payload.get("item")])
            if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
                raise ValueError("need 1–256 question rows")
            scores = [self.decision.score(row) for row in rows]
            if action == "score":
                return {"scores": scores}
            return {
                "scores": scores,
                "predictions": [
                    decision.prediction(
                        row, payload.get("calibration"), payload.get("threshold", 0)
                    )
                    for row in scores
                ],
            }
        if action == "calibrate":
            if not payload.get("excluded"):
                raise ValueError(
                    "supply scores of excluded training, test and regression rows"
                )
            return decision.calibrate(payload["scores"], payload["excluded"])
        if action == "eval":
            from decision_eval import evaluate

            return evaluate(
                payload["scores"],
                payload["ceiling"],
                payload.get("calibration"),
                payload.get("baseline"),
                payload.get("threshold", 0),
            )
        if action == "prepare":
            from decision_eval import prepare

            key, path = self.destination("decision-data")
            prepare(payload["rows"], path)
            return {"artifact": key, "manifest": read_json(path / "splits.json")}
        if action == "train":
            key, path = self.destination("decision")
            steps = bounded_steps(payload)
            trainer = decision.train_mlx if self.backend == "mlx" else decision.train
            trainer(
                self.decision_model,
                payload["rows"],
                path,
                steps,
                budget,
                self.decision_revision,
            )
            return {"artifact": key, "metadata": read_json(path / "specialist.json")}
        raise ValueError("unknown decision action")

    def run_forecast(self, action, payload, budget):
        import forecast

        if action == "synthetic":
            return forecast.synthetic(
                payload.get("seed", 7), payload.get("length", 128)
            )
        if self.forecast is None:
            self.forecast = forecast.load(
                self.forecast_model, self.forecast_revision, budget=budget
            )
        if action == "predict":
            return forecast.forecast(
                self.forecast, payload["item"], payload.get("horizon", 24)
            )
        if action == "backtest":
            return forecast.backtest(
                self.forecast,
                payload["series"],
                payload.get("horizon", 24),
                payload["origins"],
                payload.get("season", 24),
                budget,
            )
        if action == "train":
            key, path = self.destination("forecast")
            # Training uses a separate base; the prediction baseline remains fixed.
            model = forecast.load(
                self.forecast_model, self.forecast_revision, budget=budget
            )
            forecast.train(model, payload["rows"], path, bounded_steps(payload), budget)
            return {"artifact": key, "metadata": read_json(path / "specialist.json")}
        raise ValueError("unknown forecast action")

    def run_terminal(self, action, payload, budget):
        import terminal_model as tm
        from terminal_codec import Screen

        budget.torch()
        if action == "train":
            key, path = self.destination("terminal")
            model = tm.new_model()
            samples = tm.examples(payload["episodes"], model.config.context_length)
            if payload.get("corrections"):
                samples += tm.correction_examples(
                    payload["episodes"],
                    payload["corrections"],
                    model.config.context_length,
                )
            tm.train(model, samples, path, bounded_steps(payload), budget)
            return {"artifact": key, "metadata": read_json(path / "specialist.json")}
        if self.terminal is None:
            if self.terminal_model is None:
                raise ValueError(
                    "train a terminal artifact, then choose Use artifact; no terminal weights are loaded"
                )
            self.terminal = tm.load(self.terminal_model)
        if action == "eval":
            from terminal_eval import evaluate

            return evaluate(
                self.terminal,
                payload["episodes"],
                payload["ceiling"],
                budget,
                payload.get("parallel", False),
            )
        if action == "predict":
            key = payload.get("session")
            if not key:
                if len(self.sessions) >= 8:
                    self.sessions.pop(next(iter(self.sessions)))
                key = uuid.uuid4().hex
                screen = (
                    Screen.from_dict(payload["screen"])
                    if payload.get("screen")
                    else Screen.custom()
                )
                self.sessions[key] = tm.Session(self.terminal, screen)
            if key not in self.sessions:
                raise ValueError("terminal session expired; reset it")
            result = self.sessions[key].step(
                payload["event"], budget, payload.get("parallel", False)
            )
            return {"session": key, **result}
        raise ValueError("unknown terminal action")

    def use_artifact(self, key):
        if key not in self.artifacts:
            raise ValueError("unknown artifact in this runtime session")
        mode, path = self.artifacts[key]
        budget = Budget(60)
        if mode == "decision":
            from decision import DecisionModel

            self.decision = None
            self.decision = DecisionModel(
                self.decision_model if self.backend == "mlx" else str(path),
                self.backend,
                self.decision_revision if self.backend == "mlx" else None,
                budget=budget,
                adapter=str(path) if self.backend == "mlx" else None,
            )
        elif mode == "forecast":
            import forecast

            self.forecast = forecast.load(str(path), budget=budget)
        elif mode == "terminal":
            import terminal_model as tm

            budget.torch()
            self.terminal = tm.load(path)
            self.sessions.clear()
        else:
            raise ValueError("this artifact is data, not a model")
        return {"mode": mode, "active_artifact": key, "quality": "unqualified"}


def bounded_steps(payload):
    steps = payload.get("steps", 1)
    if not isinstance(steps, int) or not 1 <= steps <= 200:
        raise ValueError(
            "browser training accepts 1–200 steps; use a scoped CLI recipe for more"
        )
    return steps


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, runtime, web_root, **kwargs):
        self.runtime = runtime
        self.web_root = web_root
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass

    def send_json(self, status, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.allowed_host():
            self.send_json(403, {"error": "use the runtime's 127.0.0.1 address"})
            return
        path = urlsplit(self.path).path
        if path == "/api/specialists/health":
            self.send_json(
                200,
                {
                    "ready": True,
                    "backend": self.runtime.backend,
                    "terminal_loaded": self.runtime.terminal is not None
                    or self.runtime.terminal_model is not None,
                },
            )
            return
        if path.startswith("/api/specialists/artifacts/"):
            key = path.rsplit("/", 1)[-1]
            if key not in self.runtime.artifacts:
                self.send_json(
                    404, {"error": "artifact is not available in this runtime"}
                )
                return
            _, artifact = self.runtime.artifacts[key]
            # Export metadata for inspection. Checkpoints stay in their local
            # package folders and are never serialized as browser JSON.
            metadata = artifact / (
                "specialist.json"
                if (artifact / "specialist.json").exists()
                else "splits.json"
            )
            self.send_json(200, read_json(metadata))
            return
        relative = unquote(path).lstrip("/")
        target = (self.web_root / relative).resolve()
        if target.is_dir():
            target = target / "index.html"
        elif not target.is_file() and not target.suffix:
            target = target.with_suffix(".html")
        if not target.is_relative_to(self.web_root) or not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (
            not self.allowed_host()
            or self.headers.get("Origin") != origin
            or self.headers.get("Content-Type", "").split(";", 1)[0]
            != "application/json"
        ):
            self.send_json(
                403, {"error": "only same-origin JSON requests are accepted"}
            )
            return
        if not self.runtime.lock.acquire(blocking=False):
            self.send_json(409, {"error": "another specialist operation is running"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024 * 1024:
                raise ValueError("request must contain 1 byte–1 MiB of JSON")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            parts = urlsplit(self.path).path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "specialists"]:
                raise ValueError("unknown specialist endpoint")
            if parts[2:] == ["artifact", "use"]:
                result = self.runtime.use_artifact(payload["artifact"])
            else:
                result = self.runtime.run(parts[2], parts[3], payload)
            self.send_json(200, result)
        except (
            ValueError,
            KeyError,
            TypeError,
            OSError,
            RuntimeError,
            ImportError,
        ) as error:
            self.send_json(422, {"error": str(error)})
        finally:
            self.runtime.lock.release()


def handler(runtime, web_root):
    return partial(Handler, runtime=runtime, web_root=web_root)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--web-root", type=Path, default=ROOT / "browser" / "dist")
    parser.add_argument("--decision-model", default="mlx-community/Qwen3-1.7B-4bit")
    parser.add_argument(
        "--decision-revision", default="3b1b1768f8f8cf8351c712464f906e86c2b8269e"
    )
    parser.add_argument("--backend", choices=("mlx", "torch"), default="mlx")
    parser.add_argument("--forecast-model", default="mistralai/Timestral-5M")
    parser.add_argument(
        "--forecast-revision", default="bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f"
    )
    parser.add_argument("--terminal-model", type=Path)
    args = parser.parse_args()
    web_root = args.web_root.resolve()
    if not any(
        path.is_file()
        for path in (
            web_root / "playground" / "index.html",
            web_root / "playground.html",
        )
    ):
        parser.error("build the browser first: pnpm --dir browser run build")
    runtime = LabRuntime(
        args.decision_model,
        args.decision_revision,
        args.forecast_model,
        args.forecast_revision,
        args.terminal_model,
        args.backend,
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(runtime, web_root))
    print(
        f"Specialist modes: http://127.0.0.1:{server.server_port}/playground#specialists",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
