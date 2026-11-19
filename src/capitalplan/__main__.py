"""Command line entry: python -m capitalplan FILE.csv --start 2027."""

from __future__ import annotations

import argparse
import sys

from .plan import build_plan, format_plan, read_assets


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns 0 on success, 1 on bad input."""
    parser = argparse.ArgumentParser(prog="capitalplan", description="Five-year capital plan builder")
    parser.add_argument("file")
    parser.add_argument("--start", type=int, required=True, help="first year of the plan")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--inflation", type=float, default=0.03, help="yearly rate, 0.03 means 3 percent")
    parser.add_argument("--cap", type=float, default=None, help="maximum spend per year")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(read_assets(args.file), args.start, args.years, args.inflation, args.cap)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(format_plan(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
