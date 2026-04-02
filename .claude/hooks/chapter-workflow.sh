#!/bin/bash
# Chapter Workflow Enforcement Hook
# Triggered on PostToolUse for Write/Edit operations
# Tracks the 3-step chapter generation workflow:
#   Step 1: Context assembly (Python script) — not tracked
#   Step 2: Chapter generation → chapter_NNN.md written
#   Step 3: Update story_log.md + story_graph.md (main agent)

PENDING_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.chapter_pending"

# Read hook input from stdin
INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('file', '')))
" 2>/dev/null)

FILENAME=$(basename "$FILE_PATH" 2>/dev/null)

# Case 1: Chapter file written → create pending marker
if [[ "$FILENAME" =~ ^chapter_[0-9]+\.md$ ]]; then
    CHAPTER_NUM=$(echo "$FILENAME" | grep -o '[0-9]\+')
    echo "{\"chapter\": \"$CHAPTER_NUM\", \"log_done\": false}" > "$PENDING_FILE"
    echo "WORKFLOW: Chapter $CHAPTER_NUM written. Now update story_log + story_graph." >&2
    exit 0
fi

# Case 2: story_log.md edited → mark done (graph update is part of same step)
if [[ "$FILENAME" == "story_log.md" ]] && [[ -f "$PENDING_FILE" ]]; then
    RESULT=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    d = json.load(f)
d['log_done'] = True
print(d['chapter'])
" 2>/dev/null)
    rm -f "$PENDING_FILE"
    echo "WORKFLOW COMPLETE: Chapter $RESULT done." >&2
    exit 0
fi

exit 0
