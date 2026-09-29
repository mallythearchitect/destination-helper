#!/usr/bin/env python3
"""Refuse to commit anything that looks like a key. Standard library only, so it
runs everywhere: the pre-commit hook, CI, and by hand.

    python scripts/check_secrets.py            # staged files
    python scripts/check_secrets.py --all      # every tracked file
    python scripts/check_secrets.py path ...   # given files
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}"),
    "Mapillary token": re.compile(r"MLY\|\d{6,}\|[0-9a-f]{20,}"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}"),
    "Slack token": re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Stripe key": re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{20,}"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "Assigned secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"][A-Za-z0-9_\-/+.]{16,}['\"]"),
}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".db", ".woff", ".woff2"}
SKIP_PATH = {".env.example", "scripts/check_secrets.py"}


def files_from_git(all_files: bool) -> list[str]:
    args = ["git", "ls-files"] if all_files else ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln]


def scan(path: str) -> list[tuple[int, str]]:
    p = pathlib.Path(path)
    if not p.is_file() or p.suffix.lower() in SKIP_SUFFIX or path in SKIP_PATH:
        return []
    if p.name == ".env" or p.name.startswith(".env."):
        return [(0, "a .env file must never be committed")]
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for label, rx in PATTERNS.items():
            if rx.search(line):
                hits.append((i, label))
    return hits


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--all":
        files = files_from_git(True)
    elif argv:
        files = argv
    else:
        files = files_from_git(False)
    bad = 0
    for f in files:
        for line, label in scan(f):
            print(f"{f}:{line}: looks like a {label}")
            bad += 1
    if bad:
        print(f"\n{bad} possible secret(s). Move it to .env and reference it by name.", file=sys.stderr)
        return 1
    print(f"secrets check: {len(files)} file(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
