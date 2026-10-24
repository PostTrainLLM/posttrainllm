"""Same-origin loopback bridge for the existing browser lab's specialist modes.

Serves only built public assets; model/data paths are operator-selected or
generated, never accepted as HTTP file paths. No CORS or shell execution.
Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import argparse
import gc
import json
import mimetypes
import signal
import threading
import uuid
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import Budget, ROOT, read_json
from jobs import Jobs, atomic


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
        self.configure_workspace(restore=False)

    @classmethod
    def from_snapshot(cls, config, restore=True):
        config = dict(config)
        state_root = config.pop("state_root", None)
        runtime = cls(**config)
        runtime.configure_workspace(state_root, restore)
        return runtime

    def configure_workspace(self, state_root=None, restore=True):
        self.state_root = Path(
            state_root or ROOT / "runs" / "specialist-labs" / "web"
        ).resolve()
        self.active_artifacts = {}
        self.selection = {"decision": "qwen-1.7b", "forecast": "timestral-5m"}
        self.jobs = None
        self.budget = None
        if restore and (self.state_root / "workspace.json").is_file():
            state = read_json(self.state_root / "workspace.json")
            self.selection.update(state.get("selection", {}))
            self.active_artifacts = state.get("active_artifacts", {})
            for key in self.selection.values():
                self.select_model(key, persist=False)

    def manager(self):
        if self.jobs is None:
            self.jobs = Jobs(self.state_root / "jobs")
        return self.jobs

    def save_workspace(self):
        atomic(
            self.state_root / "workspace.json",
            {"selection": self.selection, "active_artifacts": self.active_artifacts},
        )

    def artifact_path(self, key, mode=None):
        if (
            not isinstance(key, str)
            or len(key) != 32
            or any(c not in "0123456789abcdef" for c in key)
        ):
            raise ValueError("invalid artifact id")
        if key not in self.artifacts:
            candidates = list((self.state_root / key).glob("*/specialist.json"))
            if len(candidates) != 1:
                raise ValueError("saved artifact is missing or incomplete")
            metadata = candidates[0]
            path = metadata.parent.resolve()
            if not path.is_relative_to(self.state_root):
                raise ValueError("artifact escapes this workspace")
            kind = path.name
            run_id = read_json(metadata).get("run_id")
            if run_id:
                state = read_json(self.state_root / "jobs" / run_id / "state.json")
                if state["status"] != "completed":
                    raise ValueError(
                        "artifact belongs to an incomplete or cancelled run"
                    )
            self.artifacts[key] = (kind, path)
        kind, path = self.artifacts[key]
        if mode and kind != mode:
            raise ValueError("artifact belongs to another model type")
        return path

    def select_model(self, key, persist=True):
        from model_catalog import get

        spec = get(key)
        mode = spec["mode"]
        self.selection[mode] = key
        if mode == "decision":
            self.decision_model, self.decision_revision = spec["repo"], spec["revision"]
            self.backend = spec["backend"]
            self.decision = None
        else:
            self.forecast_model, self.forecast_revision = spec["repo"], spec["revision"]
            self.forecast = None
        if persist:
            self.active_artifacts.pop(mode, None)
            self.save_workspace()
        gc.collect()
        return {"mode": mode, "model": key}

    def snapshot(self):
        return {
            "decision_model": self.decision_model,
            "decision_revision": self.decision_revision,
            "forecast_model": self.forecast_model,
            "forecast_revision": self.forecast_revision,
            "terminal_model": str(self.terminal_model) if self.terminal_model else None,
            "backend": self.backend,
            "state_root": str(self.state_root),
        }

    def start_job(self, mode, action, payload):
        if action not in ("train", "compare", "ceiling", "download"):
            raise ValueError("unknown background operation")
        if action == "train":
            bounded_steps(payload)
        if action != "download" and mode not in ("decision", "forecast", "terminal"):
            raise ValueError("unknown model type")
        if action == "compare":
            payload = {
                **payload,
                "artifact": payload.get("artifact") or self.active_artifacts.get(mode),
            }
            self.artifact_path(payload["artifact"], mode)
        if action == "download":
            from model_catalog import get

            get(payload["model"])
            mode = "model"
        if mode not in ("decision", "forecast", "terminal", "model"):
            raise ValueError("unknown model type")
        # Free parent model references before the child performs an update.
        self.decision = self.forecast = self.terminal = None
        self.sessions.clear()
        gc.collect()
        return self.manager().start(
            {
                "mode": mode,
                "action": action,
                "payload": payload,
                "runtime": self.snapshot(),
                "selection": self.selection.copy(),
            }
        )

    def workspace(self):
        from model_catalog import MODELS, readiness

        manager = self.manager()
        runs = manager.list()
        artifacts = []
        for row in runs:
            marker = manager.folder(row["run_id"]) / "artifact.json"
            if row["status"] == "completed" and marker.is_file():
                key = read_json(marker)["artifact"]
                try:
                    path = self.artifact_path(key, row["mode"])
                    artifacts.append(
                        {
                            "id": key,
                            "mode": row["mode"],
                            "run_id": row["run_id"],
                            "created_at": row["created_at"],
                            "steps": read_json(path / "specialist.json")["steps"],
                        }
                    )
                except (ValueError, OSError, KeyError):
                    pass
        return {
            "models": [readiness(k) for k in MODELS],
            "selection": self.selection,
            "active_artifacts": self.active_artifacts,
            "runs": runs,
            "artifacts": artifacts,
        }

    def destination(self, mode):
        key = uuid.uuid4().hex
        path = self.state_root / key / mode
        self.artifacts[key] = (mode, path)
        return key, path

    def run(self, mode, action, payload):
        budget = self.budget or Budget(60)
        if mode == "decision":
            result = self.run_decision(action, payload, budget)
        elif mode == "forecast":
            result = self.run_forecast(action, payload, budget)
        elif mode == "terminal":
            result = self.run_terminal(action, payload, budget)
        else:
            raise ValueError("unknown specialist mode")
        return {"result": result, "measurements": budget.measurements()}

    def decision_backend(self, budget):
        from decision import DecisionModel

        model, revision = self.decision_model, self.decision_revision
        adapter = None
        active = self.active_artifacts.get("decision")
        if active:
            path = str(self.artifact_path(active, "decision"))
            if self.backend == "mlx":
                adapter = path
            else:
                model, revision = path, None
        return DecisionModel(
            model, self.backend, revision, budget=budget, adapter=adapter
        )

    def run_decision(self, action, payload, budget):
        import decision

        if action in ("predict", "score"):
            if self.decision is None:
                self.decision = self.decision_backend(budget)
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
            active = self.active_artifacts.get("forecast")
            self.forecast = forecast.load(
                str(self.artifact_path(active, "forecast"))
                if active
                else self.forecast_model,
                None if active else self.forecast_revision,
                budget=budget,
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
            if self.active_artifacts.get("terminal"):
                self.terminal_model = self.artifact_path(
                    self.active_artifacts["terminal"], "terminal"
                )
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
        self.artifact_path(key)
        mode, path = self.artifacts[key]
        metadata = read_json(path / "specialist.json")
        self.restore_artifact_base(metadata, mode)
        if mode == "decision":
            if metadata.get("kind") == "decision-mlx-adapter":
                self.decision_model = metadata["base_model"]
                self.decision_revision = metadata["revision"]
                self.backend = "mlx"
            else:
                self.backend = "torch"
            self.decision = None
        elif mode == "forecast":
            self.forecast = None
        elif mode == "terminal":
            self.terminal = None
            self.terminal_model = path
            self.sessions.clear()
        else:
            raise ValueError("this artifact is data, not a model")
        self.active_artifacts[mode] = key
        self.save_workspace()
        return {"mode": mode, "active_artifact": key, "quality": "unqualified"}

    def restore_artifact_base(self, metadata, mode):
        run_id = metadata.get("run_id")
        if not run_id:
            return
        request = read_json(self.manager().folder(run_id) / "request.json")
        selected = request.get("selection", {}).get(mode)
        if selected and mode != "terminal":
            self.select_model(selected, persist=False)


def bounded_steps(payload):
    steps = payload.get("steps", 1)
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 200:
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

    def get_job(self, path):
        parts = path.strip("/").split("/")
        try:
            manager = self.runtime.manager()
            key = parts[3]
            if len(parts) == 5 and parts[4] in (
                "report-card.json",
                "report-card.html",
            ):
                if manager.read(key)["status"] != "completed":
                    raise ValueError("report is not complete")
                report = manager.folder(key) / "report" / parts[4]
                data = report.read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8"
                    if report.suffix == ".html"
                    else "application/json",
                )
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'",
                )
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_json(200, manager.read(key, recipe=True))
        except (ValueError, OSError, KeyError) as error:
            self.send_json(404, {"error": str(error)})

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
        if path == "/api/specialists/workspace":
            try:
                self.send_json(200, self.runtime.workspace())
            except (ValueError, OSError) as error:
                self.send_json(422, {"error": str(error)})
            return
        if path.startswith("/api/specialists/jobs/"):
            self.get_job(path)
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
        self.serve_asset(path)

    def serve_asset(self, path):
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

    def parse_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 1024 * 1024:
            raise ValueError("request must contain 1 byte–1 MiB of JSON")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("request must be a JSON object")
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["api", "specialists"]:
            raise ValueError("unknown specialist endpoint")
        return payload, parts

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
            payload, parts = self.parse_payload()
            if parts[2:] == ["jobs", "cancel"]:
                result = self.runtime.manager().cancel(payload["run_id"])
            elif self.runtime.jobs and self.runtime.jobs.active:
                self.send_json(
                    409, {"error": "a background job is running; wait or cancel it"}
                )
                return
            elif parts[2:] == ["jobs", "start"]:
                result = self.runtime.start_job(
                    payload["mode"], payload["action"], payload["input"]
                )
            elif parts[2:] == ["data", "inspect"]:
                from data_tools import inspect

                result = inspect(payload)
            elif parts[2:] == ["model", "select"]:
                result = self.runtime.select_model(payload["model"])
            elif parts[2:] == ["artifact", "use"]:
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
    parser.add_argument("--state-root", type=Path, help="isolated local run workspace")
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
    runtime.configure_workspace(args.state_root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(runtime, web_root))

    def stop_runtime(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_runtime)
    print(
        f"Specialist modes: http://127.0.0.1:{server.server_port}/playground#specialists",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if runtime.jobs:
            runtime.jobs.close()
        server.server_close()


if __name__ == "__main__":
    main()
