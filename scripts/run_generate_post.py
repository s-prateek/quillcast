#!/usr/bin/env python3
"""Run generate_post locally against your deployed AWS resources."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambdas", "generate_post"))

from handler import generate_post  # noqa: E402


def main() -> None:
    if not os.environ.get("CONFIG_BUCKET") and not os.environ.get("QUILLCAST_CONFIG_BUCKET"):
        print(
            "Set CONFIG_BUCKET or QUILLCAST_CONFIG_BUCKET (and optionally DRAFTS_TABLE_NAME).",
            file=sys.stderr,
        )
        sys.exit(1)

    result = generate_post()
    print(result)


if __name__ == "__main__":
    main()
