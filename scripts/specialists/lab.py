"""One operator entry point for the three Mac-local specialist modes.

Run through the isolated environment described in docs/factory/specialist-labs.md.
"""

import argparse
import importlib
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("decision", "forecast", "terminal", "serve"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.argv = [f"lab.py {args.mode}", *args.arguments]
    importlib.import_module("server" if args.mode == "serve" else args.mode).main()


if __name__ == "__main__":
    main()
