#!/usr/bin/env bash
# Sales Command Center — development startup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create .tmp dirs if missing
mkdir -p .tmp/sessions

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Install deps if needed
if ! python3 -c "import flask" &>/dev/null; then
  echo "Installing Python dependencies..."
  pip3 install -r requirements.txt
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       Sales Command Center — Dev Mode        ║"
echo "║  Shell: http://localhost:${PORT:-5000}                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

export FLASK_APP=shell/app.py
export FLASK_DEBUG=1
export PYTHONPATH="$SCRIPT_DIR/engine"

python3 shell/app.py
