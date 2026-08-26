#!/bin/bash
# Install (or reinstall) the periodic NAS rolling-log refresh (last 500 lines, every 60s).
# Manual stop: launchctl bootout "gui/$(id -u)/dev.pithos.logsync"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="dev.pithos.logsync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCRIPT="$ROOT/harness/scripts/sync_nas_logs.sh"
LOGS_ROOT="$HOME/logs/pithos"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$SCRIPT</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$ROOT</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>HOME</key>
		<string>$HOME</string>
		<key>PATH</key>
		<string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
	</dict>
	<key>StartInterval</key>
	<integer>60</integer>
	<key>StandardOutPath</key>
	<string>$LOGS_ROOT/runtime/launchd-logsync.stdout.log</string>
	<key>StandardErrorPath</key>
	<string>$LOGS_ROOT/runtime/launchd-logsync.stderr.log</string>
</dict>
</plist>
EOF
chmod 600 "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
echo "installed and started $LABEL (every 60s)"
