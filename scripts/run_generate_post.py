#!/usr/bin/env python3
"""Generate a draft locally using config/ and data/drafts/."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from shared.generate import generate_post  # noqa: E402


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "claude").strip().lower()
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY (or LLM_PROVIDER=gemini with GEMINI_API_KEY).", file=sys.stderr)
        sys.exit(1)
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY (or LLM_PROVIDER=claude with ANTHROPIC_API_KEY).", file=sys.stderr)
        sys.exit(1)

    result = generate_post()
    print(result)


if __name__ == "__main__":
    main()
