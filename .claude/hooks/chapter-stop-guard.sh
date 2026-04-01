#!/bin/bash
# Stop Guard Hook
# Prevents Claude from stopping if a chapter workflow is incomplete.
# Exit code 2 = block the stop action.

PENDING_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.chapter_pending"

if [[ -f "$PENDING_FILE" ]]; then
    RESULT=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    d = json.load(f)
missing = []
if not d.get('log_done'):
    missing.append('Step 3 (update story_log.md)')
if not d.get('graph_done'):
    missing.append('Step 4 (update story_graph.md)')
if missing:
    print('INCOMPLETE')
    print(d.get('chapter', '?'))
    print(' and '.join(missing))
else:
    print('COMPLETE')
" 2>/dev/null)

    STATUS=$(echo "$RESULT" | head -1)
    if [[ "$STATUS" == "INCOMPLETE" ]]; then
        CHAPTER_NUM=$(echo "$RESULT" | sed -n '2p')
        MISSING=$(echo "$RESULT" | sed -n '3p')
        echo "BLOCKED: Chapter $CHAPTER_NUM workflow incomplete. Missing: $MISSING" >&2
        echo "Complete ALL steps before stopping. See pipeline.md for the protocol." >&2
        exit 2
    fi
fi

exit 0
