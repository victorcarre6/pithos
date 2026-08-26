#!/bin/bash
# Refresh a rolling window of recent pithos log lines on the NAS for a dashboard to tail.
# No history is kept: each destination file is overwritten with only the last $LINES lines.
# Fully independent of the pithos runner/collector: a failure here (NAS unmounted, network
# hiccup) never touches them.
set -euo pipefail

LINES=500
LOGS_ROOT="$HOME/logs/pithos"
DEST="$HOME/nas/logs/pithos"

if [ ! -d "$HOME/nas/logs" ]; then
    echo "NAS not mounted at $HOME/nas, skipping sync"
    exit 0
fi

mkdir -p "$DEST"

sync_tail() {
    local source="$1" name="$2"
    [ -f "$source" ] || return 0
    tail -n "$LINES" "$source" > "$DEST/$name.log.tmp"
    mv "$DEST/$name.log.tmp" "$DEST/$name.log"
}

sync_tail "$LOGS_ROOT/live.log" "live"
sync_tail "$LOGS_ROOT/runtime/git.stderr.log" "git"
sync_tail "$LOGS_ROOT/runtime/telegram.stderr.log" "telegram"
sync_tail "$LOGS_ROOT/runtime/harness.stderr.log" "harness"
