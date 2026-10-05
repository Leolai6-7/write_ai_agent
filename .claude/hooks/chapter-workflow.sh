#!/bin/bash
# Track chapter writes per story; log edits never imply graph completion.
set -u
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PYTHON="${NOVEL_PYTHON:-python3}"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]] && [[ -z "${NOVEL_PYTHON:-}" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi
exec "$PYTHON" "$PROJECT_DIR/scripts/chapter_workflow.py" post-tool --project-dir "$PROJECT_DIR"
