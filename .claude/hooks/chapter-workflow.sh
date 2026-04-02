#!/bin/bash
# Chapter Workflow Enforcement Hook
# Triggered on PostToolUse for Write/Edit operations
# Tracks the 3-step pipeline and auto-triggers post-processing.

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

# Case 2: story_log.md edited → workflow complete + auto post-processing
if [[ "$FILENAME" == "story_log.md" ]] && [[ -f "$PENDING_FILE" ]]; then
    CHAPTER_NUM=$(python3 -c "
import json
with open('$PENDING_FILE') as f:
    print(json.load(f)['chapter'])
" 2>/dev/null)
    rm -f "$PENDING_FILE"

    # Auto-trigger post-processing in background
    STORY_DIR=$(python3 -c "
import pathlib
p = pathlib.Path('$FILE_PATH')
# story_log.md is in runtime/, go up two levels to get story dir
print(p.parent.parent)
" 2>/dev/null)

    if [[ -n "$STORY_DIR" ]] && [[ -d "$STORY_DIR" ]]; then
        CHAPTER_FILE="$STORY_DIR/outputs/chapter_$(printf '%03d' $CHAPTER_NUM).md"
        # Index chapter to ChromaDB
        cd "$CLAUDE_PROJECT_DIR" && python3 scripts/index_chapter.py --story-dir "$STORY_DIR" --chapter-num "$CHAPTER_NUM" --chapter-file "$CHAPTER_FILE" > /dev/null 2>&1 &
        # Sync graph to NetworkX JSON
        cd "$CLAUDE_PROJECT_DIR" && python3 scripts/sync_graph.py --story-dir "$STORY_DIR" > /dev/null 2>&1 &
        echo "WORKFLOW COMPLETE: Chapter $CHAPTER_NUM done. Post-processing triggered." >&2
        echo "REMINDER: If this chapter introduced new locations or settings, update story_graph.md 地點使用表/數值設定表." >&2
    else
        echo "WORKFLOW COMPLETE: Chapter $CHAPTER_NUM done. (post-processing skipped: story dir not found)" >&2
    fi
    exit 0
fi

exit 0
