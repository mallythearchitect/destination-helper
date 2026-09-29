#!/bin/sh
# Installs (or reinstalls) the nightly backup as a macOS launchd agent at the
# time in Settings → Backup. Re-run after changing that time.
#   scripts/install_backup_schedule.sh            install
#   scripts/install_backup_schedule.sh --remove   uninstall
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LABEL=com.destination-helper.backup
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

if [ "$1" = "--remove" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"; echo "removed $LABEL"; exit 0
fi

TIME=$("$PY" -c "from engine.store import Store; from engine import settings; s=Store(); print(settings.get_value(s,'backup.time')); s.close()")
HOUR=${TIME%%:*}; MIN=${TIME##*:}
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/vault/logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$ROOT/scripts/backup.py</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$((10#$HOUR))</integer><key>Minute</key><integer>$((10#$MIN))</integer></dict>
  <key>StandardOutPath</key><string>$ROOT/vault/logs/backup.log</string>
  <key>StandardErrorPath</key><string>$ROOT/vault/logs/backup.err</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL: nightly at $TIME → $ROOT/vault/backups (log: vault/logs/backup.log)"
