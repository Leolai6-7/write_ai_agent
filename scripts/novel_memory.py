"""Explicit optional Jev-Mem capture/recall for a single novel."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.jev_bridge import MemoryBridgeError, memory_status, query_memory, sync_chapter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story-dir", required=True, type=Path)
    commands = parser.add_subparsers(dest="action", required=True)
    sync = commands.add_parser("sync", help="Capture one completed chapter's log observation")
    sync.add_argument("--chapter", required=True, type=int)
    sync.add_argument("--rebuild", action="store_true", help="Rebuild only already captured, still-valid observations")
    query = commands.add_parser("query", help="Recall observations strictly before a chapter")
    query.add_argument("--before-chapter", required=True, type=int)
    query.add_argument("--query", required=True)
    query.add_argument("--limit", type=int, default=3)
    commands.add_parser("status")
    args = parser.parse_args()
    try:
        if args.action == "sync":
            result = sync_chapter(args.story_dir, args.chapter, rebuild=args.rebuild)
        elif args.action == "query":
            result = query_memory(args.story_dir, args.before_chapter, args.query, args.limit)
        else:
            result = memory_status(args.story_dir)
    except (MemoryBridgeError, OSError, ValueError, KeyError, TypeError) as error:
        result = {"status": "error", "error": str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result.get("status") == "error")


if __name__ == "__main__":
    raise SystemExit(main())
