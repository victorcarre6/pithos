#!/bin/bash
# Stop the autonomous experiment runner LaunchAgent (leaves the event collector running).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$ROOT/experiments/visualizer-dry-run"
EXPERIMENT_ID="$(python3 -c "import json; print(json.load(open('$WORKSPACE/.pithos.json'))['experiment_id'])")"
LABEL="dev.pithos.runner.$EXPERIMENT_ID"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -f "$PLIST" ]; then
    echo "no plist found for $LABEL ($PLIST) -- nothing to stop"
    exit 0
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || echo "$LABEL was already stopped"
echo "stopped $LABEL"
