#!/usr/bin/env bash
# Demo: vanished auth
# The spec requires the auth import. An agent refactors the login handler
# and quietly removes it. Spectate catches the missing-required finding.
set -e
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"

if ! command -v spectate &>/dev/null; then
  echo "spectate not found. Run: pip install -e '.[dev]' from $REPO_ROOT"
  exit 1
fi

echo "=== The spec: what this code is required to do ==="
cat "$DEMO_DIR/spec.yaml"
echo

echo "=== Before: developer-authored code (passes review) ==="
cat "$DEMO_DIR/views_clean.py"
echo

echo "=== Running spectate review on clean code... ==="
spectate review --spec "$DEMO_DIR/spec.yaml" --quiet "$DEMO_DIR/views_clean.py"
echo "(exit $?)"
echo

echo "=== After: agent-modified code ==="
cat "$DEMO_DIR/views_agent.py"
echo

echo "=== Running spectate review on agent code... ==="
spectate review --spec "$DEMO_DIR/spec.yaml" "$DEMO_DIR/views_agent.py" || true
