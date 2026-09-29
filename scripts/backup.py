#!/usr/bin/env python3
"""Nightly backup, run by launchd (see install_backup_schedule.sh). Talks to
the vault directly, so it works whether or not the server is up.
After the backup it runs the restore test, so every night proves the backup
can be read back."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backup  # noqa: E402
from engine.store import Store  # noqa: E402


def main() -> int:
    store = Store()
    try:
        made = backup.make_backup(store, note="nightly")
        test = backup.restore_test(store, file=made["file"])
    finally:
        store.close()
    print(json.dumps({"backup": made, "restore_test": test}, indent=1))
    return 0 if test["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
