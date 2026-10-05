"""Source-linked chapter context, separating plans, history and POV evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
import re

try:
    from .context_bundle import ContextBlock, SourceRef, build_context_bundle
    from .narrative_state import select_narrative_state
    from .source_spans import graph_source_chapters, graph_sources
    from .story_snapshot import StorySnapshot, text_hash
    from .foreshadowing import legacy_thread_number, resolve_thread, same_thread
except ImportError:
    from context_bundle import ContextBlock, SourceRef, build_context_bundle
    from narrative_state import select_narrative_state
    from source_spans import graph_source_chapters, graph_sources
    from story_snapshot import StorySnapshot, text_hash
    from foreshadowing import legacy_thread_number, resolve_thread, same_thread


DEFAULT_MAX_CHARS = 12000
def _thread_id(name: str) -> int | None:
    return legacy_thread_number(name)


def _same_thread(first: str, second: str) -> bool:
    return same_thread(first, second)


def context_budget(snapshot: StorySnapshot, override: int | None = None) -> int:
    text = snapshot.read_text(snapshot.story_dir / "planning" / "context_policy.json")
    policy = json.loads(text) if text else {}
    if not isinstance(policy, dict) or set(policy) - {"max_chars"}:
        raise ValueError("context_policy.json accepts only max_chars")
    limit = override if override is not None else policy.get("max_chars", DEFAULT_MAX_CHARS)
    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("max_chars must be an integer between 1 and 100000")
    return limit


def normalize_pov(value) -> list[str]:
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("pov must be a character name or a list of nonempty names")
    return list(dict.fromkeys(v.strip() for v in values))


def normalize_decision_points(value) -> list[dict]:
    """Validate optional plan shape, not literary quality or rationality.

    Keep supplied text and missing optional fields unchanged. This does not
    establish a character's knowledge, validate a belief, or record an event.
    """
    if not isinstance(value, list):
        raise ValueError("decision_points must be a list of mappings")
    text_fields = {"character", "choice", "trigger", "reasoning", "accepted_cost", "uncertainty"}
    output = []
    for index, item in enumerate(value):
        label = f"decision_points[{index}]"
        if not isinstance(item, Mapping) or set(item) - (text_fields | {"options"}):
            raise ValueError(f"{label} must be a mapping with supported decision fields")
        for required in ("character", "choice"):
            if not isinstance(item.get(required), str) or not item[required].strip():
                raise ValueError(f"{label}.{required} must be nonempty text")
        for name in text_fields & item.keys():
            if not isinstance(item[name], str):
                raise ValueError(f"{label}.{name} must be text")
        if "options" in item and (
            not isinstance(item["options"], list)
            or any(not isinstance(option, str) for option in item["options"])
        ):
            raise ValueError(f"{label}.options must be a list of text")
        output.append(dict(item))
    return output


def _ref(snapshot: StorySnapshot, path: Path, start: int = 1,
         end: int | None = None) -> SourceRef | None:
    text = snapshot.read_text(path)
    lines = text.splitlines()
    if not lines or start < 1 or start > len(lines):
        return None
    return SourceRef(str(path.relative_to(snapshot.story_dir)), start,
                     min(end or len(lines), len(lines)), text_hash(text))


def _refs(ref) -> tuple:
    return (ref,) if ref is not None else ()


def _log_ref(snapshot: StorySnapshot, entry: str) -> SourceRef | None:
    offset = snapshot.log_text.find(entry)
    if offset < 0:
        return None
    start = snapshot.log_text[:offset].count("\n") + 1
    return _ref(snapshot, snapshot.story_dir / "runtime" / "story_log.md",
                start, start + entry.count("\n"))


def target_length(snapshot: StorySnapshot, beat: dict) -> tuple[str, tuple]:
    value = beat.get("target_length")
    if value is not None:
        if (type(value) is not int and not isinstance(value, str)) or not str(value).strip():
            raise ValueError("target_length must be nonempty text or a positive integer")
        if type(value) is int and value <= 0:
            raise ValueError("target_length must be positive")
        return (f"{value} 字" if type(value) is int else value), ()
    path = snapshot.story_dir / "planning" / "story_brief.md"
    for number, line in enumerate(snapshot.read_text(path).splitlines(), 1):
        clean = line.replace("**", "")
        match = re.match(r"^\s*(?:[-*]\s*)?(?:章節字數|每章字數|章節長度)\s*[：:]\s*(.+?)\s*$", clean)
        if match:
            return match.group(1), _refs(_ref(snapshot, path, number, number))
    return "未設定；依使用者要求或先核對 story_brief，不套用固定字數", ()


def design_reference(snapshot: StorySnapshot, relative: str, term: str, *,
                     explicit_thread_id: bool = False) -> tuple[str, tuple]:
    """Return a bounded navigation span, never copy a current living profile."""
    path = snapshot.story_dir / relative
    lines = snapshot.read_text(path).splitlines()
    thread_heading = None
    if relative.endswith("foreshadowing.md"):
        headings = [match.group(2) for line in lines
                    if (match := re.match(r"^(#{1,6})\s+(.+)$", line))]
        thread_heading = resolve_thread(term, headings, explicit=explicit_thread_id, headings=True)
    for index, line in enumerate(lines):
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if not heading:
            continue
        matches = (heading.group(2) == thread_heading if relative.endswith("foreshadowing.md")
                   else term in heading.group(2))
        if not matches:
            continue
        level = len(heading.group(1))
        end = len(lines)
        for later in range(index + 1, len(lines)):
            next_heading = re.match(r"^(#{1,6})\s+", lines[later])
            if next_heading and len(next_heading.group(1)) <= level:
                end = later
                break
        # Navigation is deliberately bounded; expand explicitly if this range
        # is insufficient rather than fetching the complete living document.
        end = min(end, index + 40)
        return f"{term}：設計參考；可含未來／最新狀態，非章前知情證據。", _refs(_ref(snapshot, path, index + 1, end))
    return f"{term}：{relative} 未找到獨立標題；需要時搜尋名稱並只展開相關段落。", ()


def match_wiki_location(loc_name: str, wiki_stems: dict[str, Path]) -> Path | None:
    """Resolve legacy compound location names without injecting whole profiles."""
    if loc_name in wiki_stems:
        return wiki_stems[loc_name]
    stripped = loc_name.replace("永壽棋院-", "").replace("棋院外部-", "").replace("棋院對街-", "")
    core = re.sub(r"^[一二三]樓", "", stripped)
    for query in (core, stripped, loc_name):
        candidates = [(len(stem), stem, path) for stem, path in wiki_stems.items()
                      if stem in query or (query != loc_name and query in stem)]
        if candidates:
            return max(candidates)[2]
    return None


def _source_current(snapshot: StorySnapshot, chapter: int) -> bool:
    try:
        from .chapter_workflow import chapter_status
    except ImportError:
        from chapter_workflow import chapter_status
    entry = snapshot.workflow["chapters"].get(str(chapter), {})
    return (not any(entry.get(k) for k in ("context", "graph", "completion"))
            or chapter_status(snapshot.story_dir, chapter, snapshot=snapshot)["complete"])


def _add_history(blocks: list, snapshot: StorySnapshot, chapter: int, entry: str,
                 label: str, priority: int) -> None:
    """A chapter recalled through multiple paths appears only once in the package."""
    key = f"log:{chapter}"
    for index, block in enumerate(blocks):
        if block.key == key:
            if priority > block.priority:
                blocks[index] = replace(block, text=f"{label}\n{entry}", priority=priority)
            return
    blocks.append(ContextBlock(key, "continuity", f"{label}\n{entry}", priority=priority,
                               sources=_refs(_log_ref(snapshot, entry))))


def build_chapter_context(snapshot: StorySnapshot, chapter: int, beat: dict,
                          projected_graph: dict | None, recall: dict, *,
                          max_chars: int | None = None, previous_ending: str = "",
                          graph_status: str = "ok", dual_line: str = ""):
    """Build a bounded writer package; side metadata carries no omitted prose."""
    limit = context_budget(snapshot, max_chars)
    pov = normalize_pov(beat.get("pov"))
    length, length_sources = target_length(snapshot, beat)
    beat_source = beat.get("source")
    beat_refs = ()
    if beat_source:
        beat_refs = _refs(_ref(snapshot, snapshot.story_dir / beat_source["path"],
                               beat_source["start_line"], beat_source["end_line"]))
    blocks = [
        ContextBlock("boundaries", "author_intent",
                     "使用界線：本章計畫尚未發生；章前事實不等於所有角色知情。角色信念可能錯誤。\n"
                     "未標註知情＝資料未確認，不等於人物不知道。只按列出的範圍補讀原文，不整份傾印設定。\n"
                     "本包以完整條目控制字元數；省略資料見 metadata，補讀時保留分類與來源。", required=True),
        ContextBlock("chapter_intent", "author_intent",
                     f"LINE: {beat.get('line', '')}\nTARGET LENGTH: {length}\n"
                     f"POV: {', '.join(pov) if pov else '未標註；不可從出場名單推定'}\n"
                     f"OBJECTIVE: {beat.get('objective', '')}\nKEY EVENTS（計畫）: {beat.get('key_events', '')}\n"
                     f"EMOTIONAL TONE: {beat.get('tone', '')}", required=True,
                     sources=beat_refs + length_sources),
        ContextBlock("canon_boundary", "canon_as_of",
                     f"只使用第 {chapter} 章之前的文本紀錄；下列 fact 為來源標註，不是角色自動知情。", required=True),
    ]
    if "decision_points" in beat:
        decision_points = normalize_decision_points(beat["decision_points"])
        if decision_points:
            source_note = ("" if beat_refs else
                           "本章計畫來源無安全單獨行段，需針對性核對；不展開整份計畫。\n")
            blocks.append(ContextBlock(
                "decision_plan", "author_intent",
                "本章重大角色決策（作者計畫，尚未發生；不是已發生事實或角色知情紀錄）：\n"
                + source_note + json.dumps(decision_points, ensure_ascii=False, indent=2),
                required=True, sources=beat_refs,
            ))
    directives = beat.get("foreshadow_directives") or []
    # Older callers may supply only the compatibility list. Keep their identity,
    # but surface the missing action instead of inventing a plant/hint/resolve.
    thread_specs = list(directives)
    known_threads = {item["thread_id"] for item in directives}
    thread_specs.extend({"thread_id": name, "action": None, "legacy": True}
                        for name in beat.get("foreshadow_threads", []) if name not in known_threads)
    if thread_specs:
        action_labels = {"plant": "plant（植入）", "hint": "hint（暗示）", "resolve": "resolve（收束）",
                         None: "動作未指定；需核對本章計畫，不從歷史狀態推定"}
        planned = []
        for directive in thread_specs:
            action = directive.get("action")
            if action not in action_labels:
                raise ValueError("Foreshadow action must be plant, hint, or resolve")
            display = (f"｜{directive['name']}" if directive.get("name") else "")
            planned.append(f"- {directive['thread_id']}{display}：{action_labels[action]}")
        blocks.append(ContextBlock("foreshadow_plan", "author_intent",
                                   "本章伏筆動作（作者計畫，尚未發生；不是歷史進度或角色知情）：\n"
                                   + "\n".join(planned), required=True, sources=beat_refs))
    selected = select_narrative_state(snapshot, projected_graph or {}, chapter, pov)
    # A status/hash proves source consistency, not the truth of the interpretation.
    facts, minds = [], []
    for section, rows, target in (("canon_as_of", selected["canon"], facts),
                                  ("pov_knowledge", selected["pov"], minds)):
        # Prefer recent evidence within each class; do not make an ever-growing
        # lifetime of POV records mandatory. Whole omitted records stay discoverable.
        for item in sorted(rows, key=lambda row: (-row["updated_in"], row["id"])):
            source = item["source"]
            if not _source_current(snapshot, source["chapter"]):
                selected["excluded"].append({"id": item["id"], "reason": "source_needs_review"})
                continue
            label = {"fact": "事實紀錄", "knowledge": "已知紀錄", "belief": "相信（不保證真實）"}[item["kind"]]
            actor = f"{item['character']}｜" if item.get("character") else ""
            ref = SourceRef(source["path"], source["start_line"], source["end_line"], source["sha256"])
            blocks.append(ContextBlock(f"narrative:{item['id']}", section,
                                       f"{actor}{label}：{item['text']}",
                                       priority=110 if section == "pov_knowledge" else 90, sources=(ref,)))
            target.append(item["id"])
    if not facts:
        blocks.append(ContextBlock("canon_unknown", "canon_as_of",
                                   "尚無可用的明示事實卡；歷史摘要／圖譜僅作回查導航。", required=True))
    blocks.append(ContextBlock("pov_boundary", "pov_knowledge",
                               ("本章視角：" + "、".join(pov) + "；以下按篇幅選取明示知情／信念，各角色分開；未列出不代表不知道。"
                                if pov else "視角未標註：不推定任何角色已知，需先核對敘事視角。"), required=True))
    if not minds:
        blocks.append(ContextBlock("pov_unknown", "pov_knowledge",
                                   "沒有有效的角色知情／信念紀錄；缺漏是未知，不能用作者計畫補成角色記憶。", required=True))
    if selected["excluded"]:
        blocks.append(ContextBlock("narrative_exclusions", "pov_knowledge",
                                   f"另有 {len(selected['excluded'])} 筆狀態未納入（退休／來源失效／非本章視角等）；不回退舊版本。",
                                   required=True))

    graph = projected_graph or {}
    graph_excluded = []
    source_status = {}

    def append_graph(block: ContextBlock, section: str, item) -> None:
        chapters = graph_source_chapters(snapshot, chapter, section, item)
        for source_chapter in chapters:
            if source_chapter not in source_status:
                source_status[source_chapter] = _source_current(snapshot, source_chapter)
        stale = [ch for ch in chapters if not source_status[ch]]
        if stale:
            graph_excluded.append({"key": block.key, "reason": "source_needs_review", "chapters": stale})
            return
        refs = graph_sources(snapshot, chapter, section, item)
        if not refs:
            # One-line JSON and old node-link formats may not provide a safe
            # item-level span. Do not route readers to future cumulative history.
            block = replace(block, text=block.text + f"\n來源：第 {chapter} 章前圖譜投影；"
                            "無可單獨引用的安全行段，不展開整份累積圖譜。")
        blocks.append(replace(block, sources=refs))

    graph_threads = graph.get("foreshadowing") or {}
    matched_threads = {match for directive in thread_specs
                       if (match := resolve_thread(directive["thread_id"], graph_threads,
                                                   explicit=not directive.get("legacy", False))) is not None}
    for name, info in (graph.get("foreshadowing") or {}).items():
        relevant = name in matched_threads
        if not relevant and info.get("resolved_in"):
            continue
        text = (f"{'本章指定' if relevant else '背景'}伏筆 {name}：{info.get('status', '')}；"
                f"植入 {info.get('planted_in', [])}／暗示 {info.get('hinted_in', [])}／收束 {info.get('resolved_in', [])}。"
                f"來源是章前圖譜重播（<{chapter}），不是角色知情紀錄。")
        append_graph(ContextBlock(f"thread:{name}", "continuity", text,
                                  required=relevant, priority=20), "foreshadowing", name)
    for name, info in (graph.get("values") or {}).items():
        append_graph(ContextBlock(f"value:{name}", "continuity",
                                   f"數值設定 {name}：{info.get('value', '')}；{info.get('note', '')}。"
                                   "精確數字只有在敘事視角有取得依據時使用。",
                                   priority=30), "values", name)
    for index, chain in enumerate(graph.get("causal_chains") or []):
        text = (f"因果線索：ch{chain.get('cause_ch', '?')} {chain.get('cause', '')} → "
                f"ch{chain.get('effect_ch', '?')} {chain.get('effect', '')}（章前圖譜重播）")
        relevant = any(name in text for name in beat.get("characters", []))
        append_graph(ContextBlock(f"cause:{index}", "continuity", text,
                                  priority=70 if relevant else 15), "causal_chains", chain)
    for index, mirror in enumerate(graph.get("mirrors") or []):
        append_graph(ContextBlock(f"mirror:{index}", "continuity",
                                   f"敘事對照：R {mirror.get('r_line', '')} ↔ S {mirror.get('s_line', '')}",
                                   priority=10), "mirrors", mirror)
    for name, info in (graph.get("concepts") or {}).items():
        if info.get("introduced_in") is None:
            append_graph(ContextBlock(f"concept:{name}", "continuity",
                                       f"讀者尚未接觸概念「{name}」；首次使用需自然交代。這不代表角色知情狀態。",
                                       priority=25), "concepts", name)
    if graph_excluded:
        stale_chapters = sorted({ch for item in graph_excluded for ch in item["chapters"]})
        blocks.append(ContextBlock("graph_source_review", "continuity",
                                   f"有 {len(graph_excluded)} 筆圖譜條目的來源章 {stale_chapters} 待覆核；"
                                   "不沿用其數值／進度，先核對正文與差分。", required=True))
    if graph_status != "ok":
        blocks.append(ContextBlock("graph_status", "continuity",
                                   f"章前圖譜狀態：{graph_status}；不拿今日累積狀態代替历史快照。", required=True))

    logs = [(ch, entries[0]) for ch, entries in sorted(snapshot.log_entries.items())
            if ch < chapter and len(entries) == 1]
    for rank, (ch, entry) in enumerate(reversed(logs[-5:])):
        if _source_current(snapshot, ch):
            _add_history(blocks, snapshot, ch, entry, "歷史記錄（非角色知情）：", 64 - rank)
        else:
            blocks.append(ContextBlock(f"log_review:{ch}", "continuity",
                                       f"第 {ch} 章來源待覆核；不注入其摘要，需核對前情影響。", required=True))
    if previous_ending and not previous_ending.startswith("N/A"):
        match = re.search(r"from ch(\d+)", previous_ending)
        if match and _source_current(snapshot, int(match.group(1))):
            path = snapshot.chapter_path(int(match.group(1)))
            lines = snapshot.read_text(path).splitlines()
            # Keep complete trailing lines instead of clipping a sentence at 500 chars.
            start = max(1, len(lines) - 9)
            ending = "\n".join(lines[start - 1:])
            blocks.append(ContextBlock("previous_ending", "continuity",
                                       f"同敘事線前章原文結尾（非本章視角知情保證）：\n{ending}",
                                       priority=100, sources=_refs(_ref(snapshot, path, start, len(lines)))))
    other = re.search(r"##\s*第\s*(\d+)\s*章", dual_line)
    if other:
        other_chapter = int(other.group(1))
        entry = snapshot.log_entry(other_chapter)
        if entry and other_chapter < chapter and _source_current(snapshot, other_chapter):
            _add_history(blocks, snapshot, other_chapter, entry,
                         "另一敘事線近況（不等於目前角色知道）：", 75)
    backend = recall["selected_backend"]
    rows = (recall["jev_memory"].get("evidence", []) if backend == "jev-mem"
            else recall["semantic_recall"].get("results", []))
    for rank, item in enumerate(rows):
        ch = item.get("chapter", item.get("chapter_id"))
        if type(ch) is not int or not 0 < ch < chapter or not _source_current(snapshot, ch):
            continue
        # Use whole source log, not the backend's possibly clipped summary.
        entry = snapshot.log_entry(ch)
        if entry:
            label = "JEV-MEM RECALL" if backend == "jev-mem" else "SEMANTIC RECALL"
            _add_history(blocks, snapshot, ch, entry,
                         f"{label} / {backend} 召回候選（回查，不等於知情）：", 85 - rank)
    blocks.append(ContextBlock("recall_status", "continuity",
                               f"召回：{backend}；Chroma={recall['semantic_recall']['status']}；"
                               f"Jev={recall['jev_memory']['status']}。", required=True))

    for name in beat.get("characters", []):
        text, refs = design_reference(snapshot, "world/character_cast.md", name)
        blocks.append(ContextBlock(f"design_character:{name}", "reference", text, priority=40, sources=refs))
    for name, explicit in dict.fromkeys((item["thread_id"], not item.get("legacy", False))
                                        for item in thread_specs):
        text, refs = design_reference(snapshot, "planning/foreshadowing.md", name,
                                      explicit_thread_id=explicit)
        blocks.append(ContextBlock(f"design_thread:{name}", "reference", text, required=True, priority=45, sources=refs))
    for name in beat.get("locations", []):
        wiki_stems = {path.stem: path for path in sorted((snapshot.story_dir / "world" / "locations").glob("*.md"))}
        path = match_wiki_location(name, wiki_stems)
        relative = str(path.relative_to(snapshot.story_dir)) if path else "world/world_bible.md"
        text, refs = design_reference(snapshot, relative, path.stem if path else name)
        if path and path.stem != name:
            text = f"場景 {name} → {text}"
        blocks.append(ContextBlock(f"design_location:{name}", "reference", text, priority=35, sources=refs))

    bundle = build_context_bundle(blocks, max_chars=limit,
                                  title=f"CHAPTER CONTEXT PACKAGE — Chapter {chapter}: {beat.get('title', '')}")
    bundle.metadata["pov"] = pov
    bundle.metadata["narrative_status"] = selected["status"]
    bundle.metadata["narrative_excluded"] = selected["excluded"]
    bundle.metadata["graph_excluded"] = graph_excluded
    return bundle
