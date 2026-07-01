#!/usr/bin/env python3
<<<<<<< HEAD
"""Generate a draft locally using config/ and data/drafts/."""
=======
"""Run generate_post locally against your deployed AWS resources."""
>>>>>>> origin/main

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
<<<<<<< HEAD

from shared.generate import generate_post  # noqa: E402


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "claude").strip().lower()
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY (or LLM_PROVIDER=gemini with GEMINI_API_KEY).", file=sys.stderr)
        sys.exit(1)
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY (or LLM_PROVIDER=claude with ANTHROPIC_API_KEY).", file=sys.stderr)
=======
sys.path.insert(0, os.path.join(ROOT, "lambdas", "generate_post"))

from handler import generate_post  # noqa: E402


def main() -> None:
    if not os.environ.get("CONFIG_BUCKET") and not os.environ.get("QUILLCAST_CONFIG_BUCKET"):
        print(
            "Set CONFIG_BUCKET or QUILLCAST_CONFIG_BUCKET (and optionally DRAFTS_TABLE_NAME).",
            file=sys.stderr,
        )
>>>>>>> origin/main
        sys.exit(1)

    result = generate_post()
    print(result)


if __name__ == "__main__":
    main()
