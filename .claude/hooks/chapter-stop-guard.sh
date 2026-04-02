#!/bin/bash
# Stop Guard Hook
# Prevents Claude from stopping if a chapter workflow is incomplete.
# Exit code 2 = block the stop action.

PENDING_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.chapter_pending"

if [[ -f "$PENDING_FILE" ]]; then
    CHAPTER_NUM=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    d = json.load(f)
if not d.get('log_done'):
    print(d.get('chapter', '?'))
else:
    print('')
" 2>/dev/null)

    if [[ -n "$CHAPTER_NUM" ]]; then
        echo "BLOCKED: Chapter $CHAPTER_NUM — story_log + story_graph not yet updated." >&2
        exit 2
    fi
fi

exit 0
