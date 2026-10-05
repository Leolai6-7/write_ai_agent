#!/bin/bash
# Index failures are visible, but only the three required workflow steps block.
set -u
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PYTHON="${NOVEL_PYTHON:-python3}"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]] && [[ -z "${NOVEL_PYTHON:-}" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi
exec "$PYTHON" "$PROJECT_DIR/scripts/chapter_workflow.py" stop --project-dir "$PROJECT_DIR"
