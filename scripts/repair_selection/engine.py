"""Pinned stock MLX coder with explicit token/time/memory accounting."""

import json
import resource
import time

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

from calibrate import INSTRUCTION, request
from executor import clean, execute
from prepare import OUT, write


class Engine:
    def __init__(self, contract):
        self.started = time.monotonic()
        self.contract = contract
        mx.set_memory_limit(12 * 1024**3)
        mx.set_cache_limit(2 * 1024**3)
        self.model, self.tokenizer = load(
            contract["model"]["local_path"], trust_remote_code=False
        )
        self.generated = 0

    def guard(self):
        receipt = {
            "elapsed_seconds": time.monotonic() - self.started,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "mlx_peak_memory_bytes": mx.get_peak_memory(),
            "generated": self.generated,
            "paid_usd": 0,
        }
        write(OUT / "resource-usage.json", receipt)
        if (
            receipt["elapsed_seconds"] > 3600
            or receipt["peak_rss_bytes"] > 16 * 1024**3
        ):
            raise RuntimeError(
                "Frozen time/memory budget exceeded; do not publish partial accuracy."
            )

    def pool(self, task, index, round_number, prior=None, offset=0, label="shared"):
        payload = request(task)
        if prior is not None:
            payload["previous_attempt"] = prior["code"]
            payload["public_feedback"] = {
                "all_examples_pass": prior["public"]["passed"],
                "stop_reason": prior["public"]["stop_reason"],
            }
        prompt = self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": INSTRUCTION},
                {"role": "user", "content": json.dumps(payload)},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        rows = []
        for candidate in range(4):
            self.guard()
            seed = (
                self.contract["seed"] % 2**32
                + index * 100
                + round_number * 10
                + candidate
                + offset
            )
            mx.random.seed(seed)
            started = time.monotonic()
            output, last = "", None
            for response in stream_generate(
                self.model,
                self.tokenizer,
                prompt,
                max_tokens=256,
                sampler=make_sampler(temp=0.7, top_p=0.95),
            ):
                output += response.text
                last = response
            code = clean(output)
            row = {
                "task": task["id"],
                "split": task["split"],
                "round": round_number,
                "candidate": candidate,
                "seed": seed,
                "code": code,
                "raw_output": output,
                "generation_seconds": time.monotonic() - started,
                "generation_tokens": last.generation_tokens if last else 0,
                "generation_tps": last.generation_tps if last else None,
            }
            row["public"] = execute(
                code,
                task["public"],
                f"{label}-{task['id']}-r{round_number}-c{candidate}-public",
            )
            rows.append(row)
            self.generated += 1
            write(OUT / "pools" / f"{label}-{task['id']}-r{round_number}.json", rows)
        self.guard()
        print(
            f"{label} {task['id']} round {round_number}: {sum(r['public']['passed'] for r in rows)}/4 public pass",
            flush=True,
        )
        return rows
