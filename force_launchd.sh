#!/bin/bash
# Trigger one experiment wake right now, without waiting for the next interval tick.
# Requires the LaunchAgent to be loaded (see resume_launchd.sh) -- kickstart wakes an
# existing job, it does not install one.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$ROOT/experiments/visualizer-dry-run"
EXPERIMENT_ID="$(python3 -c "import json; print(json.load(open('$WORKSPACE/.pithos.json'))['experiment_id'])")"
LABEL="dev.pithos.runner.$EXPERIMENT_ID"

if ! launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "$LABEL is not loaded -- run resume_launchd.sh first"
    exit 1
fi

launchctl kickstart -k "gui/$(id -u)/$LABEL"
echo "kicked off $LABEL"
