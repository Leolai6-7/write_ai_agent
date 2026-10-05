"""NetworkX-based story graph for narrative relationship queries.

Nodes: chapters, characters, locations, events, foreshadowing threads, values
Edges: appears_in, located_in, causes, plants/hints/resolves, mirrors, established_in
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

import networkx as nx
from networkx.readwrite import json_graph

try:
    from .narrative_state import narrative_identity, validate_narrative_state, validate_narrative_updates
except ImportError:
    from narrative_state import narrative_identity, validate_narrative_state, validate_narrative_updates


def validate_chapter_diff(diff: dict, *, require_narrative_hash: bool = False) -> None:
    """Reject malformed deltas before changing any graph state."""
    if not isinstance(diff, dict):
        raise ValueError("Chapter diff must be a mapping")
    chapter = diff.get("chapter")
    if type(chapter) is not int or chapter < 1:
        raise ValueError("chapter must be a positive integer")
    sections = {
        "characters_appeared": ("name",), "locations_used": (),
        "foreshadowing_updates": ("thread", "action"),
        "causal_chains": ("cause", "effect"), "mirrors": ("r_line", "s_line"),
        "new_values": ("setting",), "concepts_introduced": ("name",),
    }
    unknown = set(diff) - {"chapter", "narrative_updates", *sections}
    if unknown:
        raise ValueError(f"Unknown diff sections: {', '.join(sorted(unknown))}")
    if "narrative_updates" in diff:
        validate_narrative_updates(diff["narrative_updates"], chapter, require_hash=require_narrative_hash)
    for section, fields in sections.items():
        items = diff.get(section, [])
        if items is None:
            items = []
        if not isinstance(items, list):
            raise ValueError(f"{section} must be a list")
        for item in items:
            if section == "locations_used" and isinstance(item, str):
                if not item.strip():
                    raise ValueError("Location name must not be empty")
                continue
            if not isinstance(item, dict):
                raise ValueError(f"{section} entries must be mappings")
            required = ("name",) if section == "locations_used" else fields
            for field in required:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError(f"{section}.{field} must be non-empty text")
            if section == "foreshadowing_updates" and item["action"] not in {"plant", "hint", "resolve"}:
                raise ValueError("Foreshadow action must be plant, hint, or resolve")
            for field in ("events", "note"):
                if field in item and not isinstance(item[field], str):
                    raise ValueError(f"{section}.{field} must be text")
            for field in ("cause_ch", "effect_ch", "chapter"):
                value = item.get(field)
                if value in (None, ""):
                    if section == "concepts_introduced" and field == "chapter" and field in item:
                        raise ValueError(
                            "concepts_introduced.chapter must reference this or an earlier chapter; "
                            "omit the field to use the current chapter"
                        )
                    continue
                if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= chapter:
                    raise ValueError(f"{section}.{field} must reference this or an earlier chapter")


def _chapter_number(value, location: str, *, optional: bool = False) -> int | None:
    if optional and value in (None, ""):
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, str))
            or not str(value).isdigit() or int(value) < 1):
        raise ValueError(f"{location} must reference a positive chapter number")
    return int(value)


def _validate_flat_shape(flat: dict) -> None:
    """Validate known fields while preserving extension fields in legacy snapshots."""
    if not isinstance(flat, dict):
        raise ValueError("Story graph must be an object")
    if "narrative_state" in flat:
        validate_narrative_state(flat["narrative_state"])
    if not isinstance(flat.get("chapters", []), list):
        raise ValueError("Story graph chapters must be a list")
    for value in flat.get("chapters", []):
        _chapter_number(value, "chapters")
    list_fields = {"characters": ("chapters",), "locations": ("chapters",),
                   "foreshadowing": ("planted_in", "hinted_in", "resolved_in"),
                   "values": (), "concepts": ()}
    for section, references in list_fields.items():
        items = {} if flat.get(section) is None else flat[section]
        if not isinstance(items, dict):
            raise ValueError(f"Story graph {section} must be an object")
        for name, item in items.items():
            if not isinstance(name, str) or not isinstance(item, dict):
                raise ValueError(f"Story graph {section} entries must be named objects")
            for field in references:
                if not isinstance(item.get(field, []), list):
                    raise ValueError(f"{section}.{field} must be a list")
                for value in item.get(field, []):
                    _chapter_number(value, f"{section}.{field}")
            if section == "concepts":
                _chapter_number(item.get("introduced_in"), "concepts.introduced_in", optional=True)
    for section, fields in {"causal_chains": ("cause_ch", "effect_ch"), "mirrors": ()}.items():
        items = [] if flat.get(section) is None else flat[section]
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError(f"Story graph {section} must be a list of objects")
        for item in items:
            for field in fields:
                _chapter_number(item.get(field), f"{section}.{field}", optional=True)


def _normalized_snapshot(flat: dict) -> dict:
    graph = StoryGraph(Path("."))
    graph._load_flat_unchecked({key: value for key, value in flat.items() if key != "_history"})
    return _ordered_snapshot(graph.to_flat())


def _ordered_snapshot(flat: dict) -> dict:
    # Edge list order is representational; custom ordered fields remain untouched.
    for section in ("causal_chains", "mirrors"):
        flat[section].sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return flat


def validate_flat_history(flat_data: dict) -> None:
    """Validate a legacy snapshot or its authoritative baseline and chapter history.

    Tracked snapshots must equal the replayed history. This pure check does not
    read/write files and rejects divergence before any graph state is changed.
    """
    _validate_flat_shape(flat_data)
    if "_history" not in flat_data:
        return
    history = flat_data["_history"]
    if (not isinstance(history, dict) or type(history.get("version")) is not int
            or history["version"] != 1):
        raise ValueError("Graph history must be an object with version 1")
    if set(history) != {"version", "baseline", "diffs"}:
        raise ValueError("Graph history requires only version, baseline, and diffs")
    baseline, diffs = history["baseline"], history["diffs"]
    _validate_flat_shape(baseline)
    if "_history" in baseline:
        raise ValueError("Graph history baseline cannot contain nested history")
    if not isinstance(diffs, dict):
        raise ValueError("Graph history diffs must be an object keyed by chapter")
    replayed = StoryGraph(Path("."))
    replayed._load_flat_unchecked(baseline)
    baseline_chapters = [data["number"] for _, data in replayed.G.nodes(data=True)
                         if data.get("type") == "chapter"]
    for key, diff in diffs.items():
        if (not isinstance(key, str) or not key.isdigit() or int(key) < 1
                or str(int(key)) != key):
            raise ValueError("Graph history diff keys must be canonical positive chapter strings")
        validate_chapter_diff(diff, require_narrative_hash=True)
        if diff["chapter"] != int(key):
            raise ValueError(f"Graph history key {key} does not match its diff chapter")
        if baseline_chapters and int(key) <= max(baseline_chapters):
            raise ValueError(f"Graph history chapter {key} overlaps the legacy baseline")
    for key in sorted(diffs, key=int):
        replayed._apply_diff(diffs[key])
    if _normalized_snapshot(flat_data) != _ordered_snapshot(replayed.to_flat()):
        raise ValueError(
            "Graph snapshot differs from baseline + chapter diffs; preserve the edited file, "
            "then apply the correction through a chapter diff or restore the generated snapshot"
        )


class StoryGraph:
    """Directed graph of narrative relationships."""

    def __init__(self, json_path: Path):
        self.path = json_path
        self.G = nx.MultiDiGraph()
        self._original = {}
        self._history = None
        self._narrative_state = {}
        self._narrative_present = False

    def load(self) -> bool:
        """Load graph from JSON. Returns False if file doesn't exist."""
        if not self.path.exists():
            return False
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and not ("nodes" in data and ("links" in data or "edges" in data)):
            self.load_flat(data)
            return True
        if isinstance(data, dict) and "_history" in data:
            raise ValueError("Tracked graph history requires the flat snapshot format")
        self.G = nx.MultiDiGraph(json_graph.node_link_graph(data, directed=True))
        self._original = {}
        self._history = None
        self._narrative_state = {}
        self._narrative_present = False
        return True

    def save(self) -> None:
        """Save graph to JSON."""
        if self._history is not None or self._narrative_present:
            self.save_flat()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json_graph.node_link_data(self.G)
        self._atomic_save(data)

    def _atomic_save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                         prefix=".story_graph-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load_flat(self, flat_data: dict) -> dict:
        """Build graph from flat JSON format (produced by progress-updater agent)."""
        validate_flat_history(flat_data)
        return self._load_flat_unchecked(flat_data)

    def _load_flat_unchecked(self, flat_data: dict) -> dict:
        """Load prevalidated data; used internally to replay without recursive checks."""
        self.G.clear()
        self._original = deepcopy(flat_data)
        self._history = deepcopy(flat_data.get("_history"))
        self._narrative_present = "narrative_state" in flat_data
        self._narrative_state = deepcopy(flat_data.get("narrative_state", {}))
        stats = {"nodes": 0, "edges": 0}

        for ch_num in flat_data.get("chapters", []):
            ch_num = int(ch_num)
            self.G.add_node(f"chapter:ch{ch_num}", type="chapter", number=ch_num)
            stats["nodes"] += 1

        for record in self._narrative_state.values():
            for ch_num in (record["introduced_in"], record["updated_in"]):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1

        # Characters
        for name, info in (flat_data.get("characters") or {}).items():
            char_id = f"character:{name}"
            self.G.add_node(char_id, type="character", name=name,
                           events=info.get("events", ""))
            stats["nodes"] += 1
            for ch_num in info.get("chapters", []):
                ch_num = int(ch_num)
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(char_id, ch_id, type="appears_in")
                stats["edges"] += 1

        # Locations
        for loc, info in (flat_data.get("locations") or {}).items():
            loc_id = f"location:{loc}"
            self.G.add_node(loc_id, type="location", name=loc,
                           description=info.get("description", ""))
            stats["nodes"] += 1
            for ch_num in info.get("chapters", []):
                ch_num = int(ch_num)
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, loc_id, type="located_in")
                stats["edges"] += 1

        # Foreshadowing
        for name, info in (flat_data.get("foreshadowing") or {}).items():
            fs_id = f"foreshadow:{name}"
            self.G.add_node(fs_id, type="foreshadow", name=name,
                           status=info.get("status", ""))
            stats["nodes"] += 1
            for ch_num in info.get("planted_in", []):
                ch_num = int(ch_num)
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="plants")
                stats["edges"] += 1
            for ch_num in info.get("hinted_in", []):
                ch_num = int(ch_num)
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="hints")
                stats["edges"] += 1
            for ch_num in info.get("resolved_in", []):
                ch_num = int(ch_num)
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="resolves")
                stats["edges"] += 1

        # Causal chains
        for chain in flat_data.get("causal_chains") or []:
            cause = chain.get("cause", "")
            effect = chain.get("effect", "")
            cause_ch = chain.get("cause_ch") or ""
            effect_ch = chain.get("effect_ch") or ""
            cause_id = f"event:{cause_ch}:{cause}"
            effect_id = f"event:{effect_ch}:{effect}"
            for event_ch in (cause_ch, effect_ch):
                if str(event_ch).isdigit() and int(event_ch) > 0:
                    self.G.add_node(f"chapter:ch{event_ch}", type="chapter", number=int(event_ch))
            if not self.G.has_node(cause_id):
                self.G.add_node(cause_id, type="event", description=cause, chapter=str(cause_ch))
                stats["nodes"] += 1
            if not self.G.has_node(effect_id):
                self.G.add_node(effect_id, type="event", description=effect, chapter=str(effect_ch))
                stats["nodes"] += 1
            extra = {key: deepcopy(value) for key, value in chain.items()
                     if key not in {"cause", "effect", "cause_ch", "effect_ch"}}
            self.G.add_edge(cause_id, effect_id, type="causes", extra_fields=extra)
            stats["edges"] += 1

        # Mirrors
        for m in flat_data.get("mirrors") or []:
            r_desc = m.get("r_line", "")
            s_desc = m.get("s_line", "")
            r_id = f"mirror_r:{r_desc}"
            s_id = f"mirror_s:{s_desc}"
            if not self.G.has_node(r_id):
                self.G.add_node(r_id, type="mirror", line="R", description=r_desc)
                stats["nodes"] += 1
            if not self.G.has_node(s_id):
                self.G.add_node(s_id, type="mirror", line="S", description=s_desc)
                stats["nodes"] += 1
            extra = {key: deepcopy(value) for key, value in m.items()
                     if key not in {"r_line", "s_line"}}
            self.G.add_edge(r_id, s_id, type="mirrors", extra_fields=extra)
            stats["edges"] += 1

        # Values
        for setting, info in (flat_data.get("values") or {}).items():
            val_id = f"value:{setting}"
            self.G.add_node(val_id, type="value", setting=setting,
                           value=info.get("value", ""), note=info.get("note", ""))
            stats["nodes"] += 1

        for name, info in (flat_data.get("concepts") or {}).items():
            self.G.add_node(f"concept:{name}", type="concept", name=name,
                            introduced_in=info.get("introduced_in"))
            introduced = info.get("introduced_in")
            if str(introduced).isdigit() and int(introduced) > 0:
                self.G.add_node(f"chapter:ch{introduced}", type="chapter", number=int(introduced))
            stats["nodes"] += 1

        return stats

    def to_flat(self) -> dict:
        """Export graph to flat JSON format (for agent consumption)."""
        known = {"characters", "locations", "foreshadowing", "causal_chains", "mirrors",
                 "values", "concepts", "chapters", "_history", "narrative_state"}
        flat = {**{k: deepcopy(v) for k, v in self._original.items() if k not in known},
            "chapters": sorted(d["number"] for _, d in self.G.nodes(data=True)
                               if d.get("type") == "chapter"),
            "characters": {},
            "locations": {},
            "foreshadowing": {},
            "causal_chains": [],
            "mirrors": [],
            "values": {},
            "concepts": {},
        }

        for node_id, data in self.G.nodes(data=True):
            ntype = data.get("type", "")
            if ntype == "character":
                name = data.get("name", "")
                chapters = sorted(
                    self.G.nodes[t].get("number", 0)
                    for _, t, ed in self.G.edges(node_id, data=True)
                    if ed.get("type") == "appears_in"
                )
                flat["characters"][name] = {
                    **self._original.get("characters", {}).get(name, {}),
                    "chapters": chapters,
                    "events": data.get("events", ""),
                }
            elif ntype == "location":
                name = data.get("name", "")
                chapters = sorted(
                    self.G.nodes[s].get("number", 0)
                    for s, _, ed in self.G.in_edges(node_id, data=True)
                    if ed.get("type") == "located_in"
                )
                flat["locations"][name] = {
                    **self._original.get("locations", {}).get(name, {}),
                    "chapters": chapters,
                    "description": data.get("description", ""),
                }
            elif ntype == "foreshadow":
                name = data.get("name", "")
                plants, hints, resolves = [], [], []
                for s, _, ed in self.G.in_edges(node_id, data=True):
                    ch_num = self.G.nodes[s].get("number", 0)
                    if ed.get("type") == "plants":
                        plants.append(ch_num)
                    elif ed.get("type") == "hints":
                        hints.append(ch_num)
                    elif ed.get("type") == "resolves":
                        resolves.append(ch_num)
                flat["foreshadowing"][name] = {
                    **self._original.get("foreshadowing", {}).get(name, {}),
                    "status": data.get("status", ""),
                    "planted_in": sorted(plants),
                    "hinted_in": sorted(hints),
                    "resolved_in": sorted(resolves),
                }
            elif ntype == "value":
                flat["values"][data.get("setting", "")] = {
                    **self._original.get("values", {}).get(data.get("setting", ""), {}),
                    "value": data.get("value", ""),
                    "note": data.get("note", ""),
                }

        # Concepts
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") == "concept":
                flat["concepts"][data.get("name", "")] = {
                    **self._original.get("concepts", {}).get(data.get("name", ""), {}),
                    "introduced_in": data.get("introduced_in"),
                }

        # Causal chains
        for u, v, ed in self.G.edges(data=True):
            if ed.get("type") == "causes":
                flat["causal_chains"].append({
                    **deepcopy(ed.get("extra_fields", {})),
                    "cause": self.G.nodes[u].get("description", u),
                    "cause_ch": self.G.nodes[u].get("chapter", ""),
                    "effect": self.G.nodes[v].get("description", v),
                    "effect_ch": self.G.nodes[v].get("chapter", ""),
                })

        # Mirrors
        for u, v, ed in self.G.edges(data=True):
            if ed.get("type") == "mirrors":
                flat["mirrors"].append({
                    **deepcopy(ed.get("extra_fields", {})),
                    "r_line": self.G.nodes[u].get("description", u),
                    "s_line": self.G.nodes[v].get("description", v),
                })

        if self._narrative_present or self._narrative_state:
            flat["narrative_state"] = deepcopy(self._narrative_state)
        if self._history is not None:
            flat["_history"] = deepcopy(self._history)
        return flat

    def save_flat(self) -> None:
        """Save graph as flat JSON format."""
        flat = self.to_flat()
        validate_flat_history(flat)
        self._atomic_save(flat)

    def apply_chapter_diff(self, diff: dict, *, replace: bool = False) -> dict:
        """Apply once, or explicitly replace a tracked chapter by replaying its history."""
        validate_flat_history(self.to_flat())
        validate_chapter_diff(diff, require_narrative_hash=True)
        for update in diff.get("narrative_updates", []):
            previous = self._narrative_state.get(update["id"])
            if previous and narrative_identity(previous) != narrative_identity(update):
                raise ValueError(f"Narrative id {update['id']} cannot change kind or character")
        ch_num = diff["chapter"]
        baseline = self.to_flat() if self._history is None else deepcopy(self._history["baseline"])
        baseline.pop("_history", None)
        diffs = {} if self._history is None else deepcopy(self._history["diffs"])
        existing = diffs.get(str(ch_num))
        if existing == diff:
            return {"nodes_added": 0, "edges_added": 0, "replayed": True}
        if existing is not None and not replace:
            raise ValueError(f"Chapter {ch_num} already has a different diff; use --replace to replay tracked history")
        baseline_graph = StoryGraph(self.path)
        baseline_graph.load_flat(baseline)
        baseline_chapters = [d["number"] for _, d in baseline_graph.G.nodes(data=True)
                             if d.get("type") == "chapter"]
        if baseline_chapters and ch_num <= max(baseline_chapters):
            raise ValueError(f"Chapter {ch_num} belongs to the legacy baseline; restore a pre-chapter graph before rebuilding")
        diffs[str(ch_num)] = deepcopy(diff)
        rebuilt = baseline_graph
        target_stats = {}
        for key in sorted(diffs, key=int):
            stats = rebuilt._apply_diff(diffs[key])
            if int(key) == ch_num:
                target_stats = stats
        self.G = rebuilt.G
        self._original = rebuilt._original
        self._narrative_state = rebuilt._narrative_state
        self._narrative_present = rebuilt._narrative_present
        self._history = {"version": 1, "baseline": baseline, "diffs": diffs}
        return {**target_stats, "replayed": False, "replaced": existing is not None}

    def flat_before(self, chapter: int) -> dict:
        """Return only facts available before a chapter, when replay history permits it."""
        validate_flat_history(self.to_flat())
        if self._history is None:
            chapters = [d["number"] for _, d in self.G.nodes(data=True) if d.get("type") == "chapter"]
            if any(n >= chapter for n in chapters):
                raise ValueError("Legacy graph has no historical snapshot for this chapter")
            return self.to_flat()
        projected = StoryGraph(self.path)
        projected.load_flat(self._history["baseline"])
        if any(d.get("number", 0) >= chapter for _, d in projected.G.nodes(data=True)
               if d.get("type") == "chapter"):
            raise ValueError("Requested chapter predates the tracked graph history")
        for key in sorted(self._history["diffs"], key=int):
            if int(key) < chapter:
                projected._apply_diff(self._history["diffs"][key])
        return projected.to_flat()

    def _apply_diff(self, diff: dict) -> dict:
        """Apply an already validated delta to an in-memory graph during replay."""
        stats = {"nodes_added": 0, "edges_added": 0}
        ch_num = diff.get("chapter")
        if not ch_num:
            return stats

        for update in diff.get("narrative_updates", []):
            previous = self._narrative_state.get(update["id"])
            if previous and narrative_identity(previous) != narrative_identity(update):
                raise ValueError(f"Narrative id {update['id']} cannot change kind or character")
            record = deepcopy(update)
            record.setdefault("status", "active")
            record["introduced_in"] = previous["introduced_in"] if previous else ch_num
            record["updated_in"] = ch_num
            self._narrative_state[record["id"]] = record
            self._narrative_present = True

        ch_id = f"chapter:ch{ch_num}"
        if not self.G.has_node(ch_id):
            self.G.add_node(ch_id, type="chapter", number=ch_num)
            stats["nodes_added"] += 1

        # Characters appeared
        for char in diff.get("characters_appeared") or []:
            name = char.get("name", "")
            if not name:
                continue
            char_id = f"character:{name}"
            if not self.G.has_node(char_id):
                self.G.add_node(char_id, type="character", name=name, events="")
                stats["nodes_added"] += 1
            # Append events
            old_events = self.G.nodes[char_id].get("events", "")
            new_events = char.get("events", "")
            if new_events:
                self.G.nodes[char_id]["events"] = (
                    f"{old_events} · {new_events}" if old_events else new_events
                )
            # Add edge if not exists
            if not self.G.has_edge(char_id, ch_id):
                self.G.add_edge(char_id, ch_id, type="appears_in")
                stats["edges_added"] += 1

        # Locations used
        for loc_name in diff.get("locations_used") or []:
            if isinstance(loc_name, dict):
                loc_name = loc_name.get("name", "")
            loc_id = f"location:{loc_name}"
            if not self.G.has_node(loc_id):
                self.G.add_node(loc_id, type="location", name=loc_name, description="")
                stats["nodes_added"] += 1
            if not self.G.has_edge(ch_id, loc_id):
                self.G.add_edge(ch_id, loc_id, type="located_in")
                stats["edges_added"] += 1

        # Foreshadowing updates
        for fs in diff.get("foreshadowing_updates") or []:
            thread = fs.get("thread", "")
            action = fs.get("action", "")
            fs_id = f"foreshadow:{thread}"
            if not self.G.has_node(fs_id):
                self.G.add_node(fs_id, type="foreshadow", name=thread, status="")
                stats["nodes_added"] += 1
            # Update status
            action_to_status = {"plant": "已植入", "hint": "已暗示", "resolve": "已收束"}
            if action in action_to_status and (
                action == "resolve" or self.G.nodes[fs_id].get("status") != "已收束"
            ):
                self.G.nodes[fs_id]["status"] = action_to_status[action]
            # Add edge
            edge_type = {"plant": "plants", "hint": "hints", "resolve": "resolves"}.get(action)
            existing_types = {d.get("type") for d in self.G.get_edge_data(ch_id, fs_id, default={}).values()}
            if edge_type and edge_type not in existing_types:
                self.G.add_edge(ch_id, fs_id, type=edge_type)
                stats["edges_added"] += 1

        # Causal chains
        for chain in diff.get("causal_chains") or []:
            cause = chain.get("cause", "")
            effect = chain.get("effect", "")
            cause_ch = chain.get("cause_ch") or ""
            effect_ch = chain.get("effect_ch") or ""
            cause_id = f"event:{cause_ch}:{cause}"
            effect_id = f"event:{effect_ch}:{effect}"
            # Match flat loading: references add nodes, not applied chapter diffs.
            for event_ch in (cause_ch, effect_ch):
                if event_ch != "":
                    event_ch_id = f"chapter:ch{event_ch}"
                    if not self.G.has_node(event_ch_id):
                        self.G.add_node(event_ch_id, type="chapter", number=int(event_ch))
                        stats["nodes_added"] += 1
            if not self.G.has_node(cause_id):
                self.G.add_node(cause_id, type="event", description=cause,
                               chapter=str(cause_ch))
                stats["nodes_added"] += 1
            if not self.G.has_node(effect_id):
                self.G.add_node(effect_id, type="event", description=effect,
                               chapter=str(effect_ch))
                stats["nodes_added"] += 1
            if not self.G.has_edge(cause_id, effect_id):
                self.G.add_edge(cause_id, effect_id, type="causes")
                stats["edges_added"] += 1

        # Mirrors
        for m in diff.get("mirrors") or []:
            r_desc = m.get("r_line", "")
            s_desc = m.get("s_line", "")
            r_id = f"mirror_r:{r_desc}"
            s_id = f"mirror_s:{s_desc}"
            if not self.G.has_node(r_id):
                self.G.add_node(r_id, type="mirror", line="R", description=r_desc)
                stats["nodes_added"] += 1
            if not self.G.has_node(s_id):
                self.G.add_node(s_id, type="mirror", line="S", description=s_desc)
                stats["nodes_added"] += 1
            if not self.G.has_edge(r_id, s_id):
                self.G.add_edge(r_id, s_id, type="mirrors")
                stats["edges_added"] += 1

        # New values
        for val in diff.get("new_values") or []:
            setting = val.get("setting", "")
            val_id = f"value:{setting}"
            self.G.add_node(val_id, type="value", setting=setting,
                           value=val.get("value", ""), note=val.get("note", ""))
            stats["nodes_added"] += 1

        # Concepts introduced
        for concept in diff.get("concepts_introduced") or []:
            name = concept.get("name", "")
            # Store as a simple attribute on a concept node
            concept_id = f"concept:{name}"
            introduced = concept.get("chapter", ch_num)
            if self.G.has_node(concept_id):
                prior = self.G.nodes[concept_id].get("introduced_in")
                if prior is not None:
                    introduced = min(int(prior), int(introduced))
            self.G.add_node(concept_id, type="concept", name=name,
                           introduced_in=introduced)
            stats["nodes_added"] += 1
            introduced_ch_id = f"chapter:ch{introduced}"
            if not self.G.has_node(introduced_ch_id):
                self.G.add_node(introduced_ch_id, type="chapter", number=int(introduced))
                stats["nodes_added"] += 1

        return stats

    # --- Query API ---

    def get_character_history(self, name: str) -> dict:
        """Get a character's appearance history and events."""
        char_id = f"character:{name}"
        if not self.G.has_node(char_id):
            return {"found": False}

        node = self.G.nodes[char_id]
        chapters = []
        for _, target, data in self.G.edges(char_id, data=True):
            if data.get("type") == "appears_in" and self.G.nodes[target].get("type") == "chapter":
                chapters.append(self.G.nodes[target].get("number", 0))

        return {
            "found": True,
            "name": name,
            "events": node.get("events", ""),
            "chapters": sorted(chapters),
        }

    def trace_causation(self, event_keyword: str, depth: int = 3) -> list[str]:
        """Trace causal chain backwards from an event."""
        # Find event nodes matching keyword
        matches = [n for n in self.G.nodes if n.startswith("event:") and event_keyword in n]
        if not matches:
            return []

        results = []
        for node in matches:
            try:
                events = self.G.subgraph([n for n in self.G.nodes if self.G.nodes[n].get("type") == "event"])
                ancestors = nx.single_source_shortest_path_length(events.reverse(), node, cutoff=depth)
                for a in ancestors:
                    if a == node:
                        continue
                    desc = self.G.nodes[a].get("description", a)
                    ch = self.G.nodes[a].get("chapter", "?")
                    results.append(f"[{ch}] {desc}")
            except (nx.NetworkXError, nx.NodeNotFound):
                pass
        return results

    def get_active_foreshadows(self) -> list[dict]:
        """Get all foreshadowing threads that haven't been resolved."""
        results = []
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") == "foreshadow":
                status = data.get("status", "")
                if "已收束" not in status and "resolved" not in status.lower():
                    # Find which chapters plant/hint/resolve this thread
                    plants, hints, resolves = [], [], []
                    for source, _, edge_data in self.G.in_edges(node_id, data=True):
                        ch_num = self.G.nodes[source].get("number", 0)
                        if edge_data.get("type") == "plants":
                            plants.append(ch_num)
                        elif edge_data.get("type") == "hints":
                            hints.append(ch_num)
                        elif edge_data.get("type") == "resolves":
                            resolves.append(ch_num)
                    results.append({
                        "name": data.get("name", node_id),
                        "status": status,
                        "planted_in": sorted(plants),
                        "hinted_in": sorted(hints),
                        "resolved_in": sorted(resolves),
                    })
        return results

    def get_foreshadow_chain(self, name_fragment: str) -> dict | None:
        """Get the full chain of a specific foreshadowing thread by name fragment."""
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") == "foreshadow" and name_fragment in data.get("name", ""):
                plants, hints, resolves = [], [], []
                for source, _, edge_data in self.G.in_edges(node_id, data=True):
                    ch_num = self.G.nodes[source].get("number", 0)
                    if edge_data.get("type") == "plants":
                        plants.append(ch_num)
                    elif edge_data.get("type") == "hints":
                        hints.append(ch_num)
                    elif edge_data.get("type") == "resolves":
                        resolves.append(ch_num)
                return {
                    "name": data.get("name", node_id),
                    "status": data.get("status", ""),
                    "planted_in": sorted(plants),
                    "hinted_in": sorted(hints),
                    "resolved_in": sorted(resolves),
                }
        return None

    def get_chapter_context(self, chapter_num: int) -> dict:
        """Get all nodes related to a chapter."""
        ch_id = f"chapter:ch{chapter_num}"
        if not self.G.has_node(ch_id):
            return {"found": False}

        characters = []
        locations = []
        foreshadows = []
        events = []
        values = []

        # Incoming edges (things pointing to this chapter)
        for source, _, data in self.G.in_edges(ch_id, data=True):
            node = self.G.nodes[source]
            edge_type = data.get("type", "")
            if edge_type == "appears_in":
                characters.append(node.get("name", source))
            elif edge_type == "occurs_in":
                events.append(node.get("description", source))
            elif edge_type == "established_in":
                values.append(f"{node.get('setting', '')} = {node.get('value', '')}")

        # Outgoing edges (things this chapter points to)
        for _, target, data in self.G.edges(ch_id, data=True):
            node = self.G.nodes[target]
            edge_type = data.get("type", "")
            if edge_type == "located_in":
                locations.append(node.get("name", target))
            elif edge_type in ("plants", "hints", "resolves"):
                foreshadows.append({"name": node.get("name", target), "action": edge_type})

        return {
            "found": True,
            "chapter": chapter_num,
            "characters": characters,
            "locations": locations,
            "foreshadows": foreshadows,
            "events": events,
            "values": values,
        }

    def get_mirrors(self) -> list[dict]:
        """Get all mirror pairs."""
        results = []
        for u, v, data in self.G.edges(data=True):
            if data.get("type") == "mirrors":
                results.append({
                    "r_line": self.G.nodes[u].get("description", u),
                    "s_line": self.G.nodes[v].get("description", v),
                })
        return results

    def get_all_values(self) -> str:
        """Get all numerical values as formatted text."""
        lines = ["| 設定 | 值 | 備註 |", "|------|-----|------|"]
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") == "value":
                lines.append(f"| {data.get('setting', '')} | {data.get('value', '')} | {data.get('note', '')} |")
        return "\n".join(lines) if len(lines) > 2 else ""

    def summary(self) -> dict:
        """Get graph statistics."""
        type_counts = {}
        for _, data in self.G.nodes(data=True):
            t = data.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        edge_counts = {}
        for _, _, data in self.G.edges(data=True):
            t = data.get("type", "unknown")
            edge_counts[t] = edge_counts.get(t, 0) + 1

        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "node_types": type_counts,
            "edge_types": edge_counts,
        }
