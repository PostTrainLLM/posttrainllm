"""Operator CLI for learned terminal data, training, prediction and replay.

Contract: docs/factory/specialist-labs.md. Predictions never execute commands.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import Budget, read_json, read_rows, write_json, write_rows
from terminal_codec import Screen
from terminal_model import (
    Session,
    correction_examples,
    examples,
    load,
    new_model,
    train,
)


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    child = sub.add_parser("recipe")
    child.add_argument("--seed", type=int, default=7)
    child.add_argument("--memory", action="store_true")
    child.add_argument("--out", required=True)
    child = sub.add_parser("record")
    child.add_argument("--recipe", required=True)
    child.add_argument(
        "--image", required=True, help="known local image with /bin/sh; never pulled"
    )
    child.add_argument("--seconds", type=float, default=60)
    child.add_argument("--out", required=True)
    child = sub.add_parser("train")
    child.add_argument("--data", required=True)
    child.add_argument("--config")
    child.add_argument("--base")
    child.add_argument(
        "--corrections", help="predicted frame JSONL for recoverable-error training"
    )
    child.add_argument("--steps", type=int, default=1)
    child.add_argument("--seconds", type=float, default=60)
    child.add_argument("--out", required=True)
    child = sub.add_parser("predict")
    child.add_argument("--model", required=True)
    child.add_argument(
        "--screen", help="custom Screen JSON; default is an 8×48 shell prompt"
    )
    child.add_argument(
        "--events", required=True, help="JSON array of raw-key / wait events"
    )
    child.add_argument("--parallel", action="store_true")
    child.add_argument("--seconds", type=float, default=60)
    child.add_argument("--out", required=True)
    child = sub.add_parser("replay")
    child.add_argument("--data", required=True)
    child = sub.add_parser("ceiling")
    child.add_argument("--data", required=True)
    child.add_argument("--out", required=True)
    child = sub.add_parser("eval")
    child.add_argument("--data", required=True)
    child.add_argument("--model", required=True)
    child.add_argument("--ceiling", required=True)
    child.add_argument("--parallel", action="store_true")
    child.add_argument("--seconds", type=float, default=60)
    child.add_argument("--out", required=True)
    child = sub.add_parser("export")
    child.add_argument("--model", required=True, type=Path)
    child.add_argument("--dtype", choices=("f32", "f16"), default="f32")
    child.add_argument("--out", required=True)
    return parser


def main():
    args = argument_parser().parse_args()
    if args.command == "export":
        from terminal_export import export

        budget = Budget()
        budget.torch()
        print(json.dumps(export(args.model, args.out, args.dtype)))
        return
    if args.command == "recipe":
        from terminal_record import synthetic_recipe

        write_json(args.out, synthetic_recipe(args.seed, memory=args.memory))
        return
    if args.command == "ceiling":
        from terminal_eval import ceiling

        ceiling(read_rows(args.data), args.out)
        return
    if args.command == "record":
        from terminal_record import record

        write_rows(
            args.out, [record(read_json(args.recipe), args.image, Budget(args.seconds))]
        )
        return
    if args.command == "replay":
        for episode in read_rows(args.data):
            print(f"Recorded oracle: {episode['id']}")
            for frame in episode["frames"]:
                print(
                    "\033[H\033[2J" + "\n".join(Screen.from_dict(frame["screen"]).lines)
                )
        return
    budget = Budget(args.seconds)
    budget.torch()
    if args.command == "eval":
        from terminal_eval import evaluate

        write_json(
            args.out,
            evaluate(
                load(args.model),
                read_rows(args.data),
                read_json(args.ceiling),
                budget,
                args.parallel,
            ),
        )
        return
    if args.command == "train":
        model = (
            load(args.base)
            if args.base
            else new_model(read_json(args.config) if args.config else None)
        )
        episodes = read_rows(args.data)
        samples = examples(episodes, model.config.context_length)
        if args.corrections:
            samples += correction_examples(
                episodes, read_rows(args.corrections), model.config.context_length
            )
        losses = train(model, samples, args.out, args.steps, budget)
        print(
            json.dumps(
                {"steps": len(losses), "last_loss": losses[-1], **budget.measurements()}
            )
        )
    else:
        screen = (
            Screen.from_dict(read_json(args.screen)) if args.screen else Screen.custom()
        )
        session = Session(load(args.model), screen)
        results = []
        for index, event in enumerate(read_json(args.events)):
            results.append(
                {"id": str(index), **session.step(event, budget, args.parallel)}
            )
        write_rows(args.out, results)
        print(json.dumps(budget.measurements()))


if __name__ == "__main__":
    main()
