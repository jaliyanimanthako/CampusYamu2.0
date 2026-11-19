"""List the prompts, or print one in full.

    uv run python -m campusyamu.prompts
    uv run python -m campusyamu.prompts course_chat
"""

from __future__ import annotations

import sys

from . import PROMPTS, get


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        width = max(map(len, PROMPTS))
        for name, (used_by, _) in PROMPTS.items():
            text = get(name)
            print(f"{name:<{width}}  {len(text):>6} chars  {used_by}")
        print("\nPrint one: uv run python -m campusyamu.prompts <name>   (edit them in src/campusyamu/prompts/)")
        return 0
    name = args[0]
    if name not in PROMPTS:
        print(f"unknown prompt {name!r}; choose from: {', '.join(PROMPTS)}", file=sys.stderr)
        return 1
    print(get(name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
