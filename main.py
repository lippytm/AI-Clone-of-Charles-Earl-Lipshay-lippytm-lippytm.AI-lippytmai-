"""
main.py — Entry point for the AI Clone Engine of Charles-Earl-Lipshay.

Usage:
    python main.py                        # interactive chat (default session)
    python main.py --session my_session   # named persistent session
    python main.py --reset                # clear session memory and start fresh
    python main.py --profile              # print personality profile and exit
    python main.py --version              # print engine version and exit
"""

from __future__ import annotations

import argparse
import sys

from engine import __version__


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lippytmai",
        description="AI Clone Engine of Charles-Earl-Lipshay",
    )
    parser.add_argument(
        "--session",
        default="default",
        metavar="NAME",
        help="Session name for persistent conversation memory (default: 'default')",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the session memory before starting",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print the active personality profile and exit",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the engine version and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.version:
        print(f"AI Clone Engine v{__version__} · lippytmai · @lippytm")
        sys.exit(0)

    from engine.core import CloneEngine
    from api.chat import run_interactive

    if args.profile:
        engine = CloneEngine(session_id=args.session)
        print(engine.profile_summary())
        sys.exit(0)

    if args.reset:
        engine = CloneEngine(session_id=args.session)
        engine.reset()
        print(f"[Engine] Session '{args.session}' memory cleared.")

    run_interactive(session_id=args.session)


if __name__ == "__main__":
    main()
