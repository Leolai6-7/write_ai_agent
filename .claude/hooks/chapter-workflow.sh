#!/bin/bash
# Chapter Workflow Enforcement Hook
# Triggered on PostToolUse for Write/Edit operations
# Tracks the 4-step chapter generation workflow:
#   Step 1: Context assembly (sub-agent) — not tracked (no file output)
#   Step 2: Chapter generation → chapter_NNN.md written
#   Step 3: Update story_log.md
#   Step 4: Update story_graph.md

PENDING_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.chapter_pending"

# Read hook input from stdin into variable
INPUT=$(cat)

# Extract file path using python (parse once)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('file', '')))
" 2>/dev/null)

# Get just the filename
FILENAME=$(basename "$FILE_PATH" 2>/dev/null)

# Case 1: Chapter file written → create pending marker
if [[ "$FILENAME" =~ ^chapter_[0-9]+\.md$ ]]; then
    CHAPTER_NUM=$(echo "$FILENAME" | grep -o '[0-9]\+')
    echo "{\"chapter\": \"$CHAPTER_NUM\", \"log_done\": false, \"graph_done\": false}" > "$PENDING_FILE"
    echo "WORKFLOW REMINDER: Chapter $CHAPTER_NUM written (Step 2 done). You MUST now complete:" >&2
    echo "  Step 3: Update story_log.md (main agent, no sub-agent)" >&2
    echo "  Step 4: Update story_graph.md (sub-agent)" >&2
    exit 0
fi

# Case 2: story_log.md edited → mark log step done
if [[ "$FILENAME" == "story_log.md" ]] && [[ -f "$PENDING_FILE" ]]; then
    RESULT=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    d = json.load(f)
d['log_done'] = True
with open('$PENDING_FILE', 'w') as f:
    json.dump(d, f)
print('complete' if d['graph_done'] else 'partial')
print(d['chapter'])
" 2>/dev/null)
    STATUS=$(echo "$RESULT" | head -1)
    CHAPTER_NUM=$(echo "$RESULT" | tail -1)

    if [[ "$STATUS" == "complete" ]]; then
        rm -f "$PENDING_FILE"
        echo "WORKFLOW COMPLETE: Chapter $CHAPTER_NUM — all 4 steps done. Ready for next chapter." >&2
    else
        echo "WORKFLOW UPDATE: Step 3 (story_log) done. Still need Step 4: Update story_graph.md" >&2
    fi
    exit 0
fi

# Case 3: story_graph.md edited → mark graph step done
if [[ "$FILENAME" == "story_graph.md" ]] && [[ -f "$PENDING_FILE" ]]; then
    RESULT=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    d = json.load(f)
d['graph_done'] = True
with open('$PENDING_FILE', 'w') as f:
    json.dump(d, f)
print('complete' if d['log_done'] else 'partial')
print(d['chapter'])
" 2>/dev/null)
    STATUS=$(echo "$RESULT" | head -1)
    CHAPTER_NUM=$(echo "$RESULT" | tail -1)

    if [[ "$STATUS" == "complete" ]]; then
        rm -f "$PENDING_FILE"
        echo "WORKFLOW COMPLETE: Chapter $CHAPTER_NUM — all 4 steps done. Ready for next chapter." >&2
    else
        echo "WORKFLOW UPDATE: Step 4 (story_graph) done. Still need Step 3: Update story_log.md" >&2
    fi
    exit 0
fi

exit 0
