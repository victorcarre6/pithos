#!/bin/zsh
set -eu

HARNESS_ROOT=${0:A:h}
REPOSITORY_ROOT=${HARNESS_ROOT:h}
EXPERIMENT_ID=""
CHECK_ONLY=0
INSTALL_SYSTEM=0

while (( $# > 0 )); do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --install-system) INSTALL_SYSTEM=1 ;;
    --experiment)
      shift
      EXPERIMENT_ID=${1:-}
      ;;
    *)
      print -u2 "unknown argument: $1"
      exit 2
      ;;
  esac
  shift
done

if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
  print -u2 "Pithos baseline requires macOS on Apple Silicon."
  exit 1
fi

if (( INSTALL_SYSTEM && ! CHECK_ONLY )); then
  if ! command -v brew >/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
  brew install git node python@3.12 ollama
  brew install --cask docker
  npm install --global @earendil-works/pi-coding-agent@0.84.2
  brew services start ollama
  open -a Docker || true
  for _ in {1..60}; do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi

missing=()
for command in git node npm ollama pi docker; do
  command -v "$command" >/dev/null || missing+=("$command")
done
PYTHON_BIN=$(command -v python3.12 || command -v python3 || command -v python || true)
[[ -n "$PYTHON_BIN" ]] || missing+=("python>=3.12")
if (( ${#missing} > 0 )); then
  print -u2 "Missing commands: ${missing[*]}"
  print -u2 "Install them explicitly before rerunning; this script never installs system software silently."
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 12), sys.version'

"$PYTHON_BIN" "$HARNESS_ROOT/scripts/bootstrap.py" \
  --project-root "$HARNESS_ROOT" \
  --repository-root "$REPOSITORY_ROOT"

if (( CHECK_ONLY )); then
  exit 0
fi

[[ -d "$HARNESS_ROOT/.venv" ]] || "$PYTHON_BIN" -m venv "$HARNESS_ROOT/.venv"
VENV_PYTHON="$HARNESS_ROOT/.venv/bin/python"
"$VENV_PYTHON" -m pip install -e "${HARNESS_ROOT}[dev]"
npm --prefix "$HARNESS_ROOT" install
npm --prefix "$HARNESS_ROOT/dashboard/web" install
npm --prefix "$HARNESS_ROOT/dashboard/web" run build

if docker info >/dev/null 2>&1; then
  docker build -t pithos-agent:local "$HARNESS_ROOT/runtime/agent"
else
  print "Docker daemon is stopped; image build deferred."
fi

if [[ -n "$EXPERIMENT_ID" ]]; then
  "$VENV_PYTHON" "$HARNESS_ROOT/scripts/create_experiment.py" "$EXPERIMENT_ID" \
    --harness-root "$HARNESS_ROOT" \
    --experiments-root "$REPOSITORY_ROOT/experiments"
fi

print "Pithos harness installed."
print "Activate commands with: source $HARNESS_ROOT/.venv/bin/activate"
