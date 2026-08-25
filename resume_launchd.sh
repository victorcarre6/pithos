#!/bin/bash
# Resume the autonomous experiment runner LaunchAgent on its normal interval schedule.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$ROOT/experiments/visualizer-dry-run"
EXPERIMENT_ID="$(python3 -c "import json; print(json.load(open('$WORKSPACE/.pithos.json'))['experiment_id'])")"
LABEL="dev.pithos.runner.$EXPERIMENT_ID"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -f "$PLIST" ]; then
    echo "no plist found for $LABEL ($PLIST) -- run install_launchd.py first"
    exit 1
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
echo "resumed $LABEL"
