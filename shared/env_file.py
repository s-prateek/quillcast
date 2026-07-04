from __future__ import annotations

import os
from pathlib import Path


def project_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def _parse_env_lines(text: str) -> list[str]:
    return text.splitlines()


def _format_env_line(key: str, value: str) -> str:
    if not value:
        return f"{key}="
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f"{key}={value}"


def upsert_env_vars(env_path: Path, updates: dict[str, str]) -> None:
    """
    Merge keys into a .env file, preserving unrelated lines and comments.

    Local-only credential storage (gitignored). Same pattern as manual .env editing.
    """
    existing = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    lines = _parse_env_lines(existing) if existing else []
    remaining = dict(updates)
    output_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output_lines.append(line)
            continue

        key = stripped.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()

        if key in remaining:
            output_lines.append(_format_env_line(key, remaining.pop(key)))
        else:
            output_lines.append(line)

    if remaining:
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.append("# Ghost Admin API (scripts/ghost_setup.py)")
        for key in sorted(remaining):
            output_lines.append(_format_env_line(key, remaining[key]))

    env_path.parent.mkdir(parents=True, exist_ok=True)
    # codeql[py/clear-text-storage-sensitive-data]: Gitignored local .env; user-owned machine.
    env_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)
