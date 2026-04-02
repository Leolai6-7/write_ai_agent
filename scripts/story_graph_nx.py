"""NetworkX-based story graph for narrative relationship queries.

Nodes: chapters, characters, locations, events, foreshadowing threads, values
Edges: appears_in, located_in, causes, plants/hints/resolves, mirrors, established_in
"""

import json
import re
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from _common import parse_md_table, PROJECT_ROOT


class StoryGraph:
    """Directed graph of narrative relationships."""

    def __init__(self, json_path: Path):
        self.path = json_path
        self.G = nx.DiGraph()

    def load(self) -> bool:
        """Load graph from JSON. Returns False if file doesn't exist."""
        if not self.path.exists():
            return False
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.G = json_graph.node_link_graph(data, directed=True, multigraph=False)
        return True

    def save(self) -> None:
        """Save graph to JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json_graph.node_link_data(self.G)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def sync_from_markdown(self, md_path: Path) -> dict:
        """Build graph from story_graph.md. Returns stats."""
        text = md_path.read_text(encoding="utf-8")
        self.G.clear()
        stats = {"nodes": 0, "edges": 0}

        self._sync_characters(text, stats)
        self._sync_locations(text, stats)
        self._sync_foreshadows(text, stats)
        self._sync_causal_chains(text, stats)
        self._sync_mirrors(text, stats)
        self._sync_values(text, stats)

        return stats

    # --- Build methods ---

    def _sync_characters(self, text: str, stats: dict) -> None:
        rows = parse_md_table(text, "## 角色出場表")
        for row in rows:
            name = row.get("角色", "").strip()
            if not name:
                continue
            chapters_str = row.get("規劃出場章節", row.get("出場章節", ""))
            events = row.get("主要事件", "")

            char_id = f"character:{name}"
            self.G.add_node(char_id, type="character", name=name, events=events)
            stats["nodes"] += 1

            for ch_num in _parse_nums(chapters_str):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(char_id, ch_id, type="appears_in")
                stats["edges"] += 1

    def _sync_locations(self, text: str, stats: dict) -> None:
        rows = parse_md_table(text, "## 地點使用表")
        for row in rows:
            loc = row.get("地點", "").strip()
            if not loc:
                continue
            chapters_str = row.get("規劃出現章節", row.get("出現章節", ""))
            desc = row.get("關鍵描述", "")

            loc_id = f"location:{loc}"
            self.G.add_node(loc_id, type="location", name=loc, description=desc)
            stats["nodes"] += 1

            for ch_num in _parse_nums(chapters_str):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, loc_id, type="located_in")
                stats["edges"] += 1

    def _sync_foreshadows(self, text: str, stats: dict) -> None:
        rows = parse_md_table(text, "## 伏筆追蹤")
        for row in rows:
            name = row.get("伏筆", "").strip()
            if not name:
                continue
            status = row.get("狀態", "")
            plant_str = row.get("植入", "")
            hint_str = row.get("暗示", "")
            resolve_str = row.get("收束", "")

            fs_id = f"foreshadow:{name}"
            self.G.add_node(fs_id, type="foreshadow", name=name, status=status)
            stats["nodes"] += 1

            for ch_num in _parse_nums(plant_str):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="plants")
                stats["edges"] += 1

            for ch_num in _parse_nums(hint_str):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="hints")
                stats["edges"] += 1

            for ch_num in _parse_nums(resolve_str):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(ch_id, fs_id, type="resolves")
                stats["edges"] += 1

    def _sync_causal_chains(self, text: str, stats: dict) -> None:
        match = re.search(r"^## 因果鏈\s*$", text, re.MULTILINE)
        if not match:
            return
        rest = text[match.end():]
        next_h = re.search(r"^## ", rest, re.MULTILINE)
        section = rest[:next_h.start()] if next_h else rest

        for line in section.strip().split("\n"):
            if not line.startswith("|") or line.startswith("|-"):
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 5 or cells[1] == "因":
                continue

            cause = cells[1]
            cause_ch = cells[2]
            effect = cells[3]
            effect_ch = cells[4]

            cause_id = f"event:{cause}"
            effect_id = f"event:{effect}"

            if not self.G.has_node(cause_id):
                self.G.add_node(cause_id, type="event", description=cause, chapter=cause_ch)
                stats["nodes"] += 1
            if not self.G.has_node(effect_id):
                self.G.add_node(effect_id, type="event", description=effect, chapter=effect_ch)
                stats["nodes"] += 1

            self.G.add_edge(cause_id, effect_id, type="causes")
            stats["edges"] += 1

            # Link events to chapters
            for ch_num in _parse_nums(cause_ch):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(cause_id, ch_id, type="occurs_in")
                stats["edges"] += 1

    def _sync_mirrors(self, text: str, stats: dict) -> None:
        rows = parse_md_table(text, "## 雙線鏡像")
        for row in rows:
            r_event = row.get("R線事件", "").strip()
            s_event = row.get("S線對應", "").strip()
            if not r_event or not s_event:
                continue

            r_id = f"mirror_r:{r_event}"
            s_id = f"mirror_s:{s_event}"

            if not self.G.has_node(r_id):
                self.G.add_node(r_id, type="mirror", line="R", description=r_event)
                stats["nodes"] += 1
            if not self.G.has_node(s_id):
                self.G.add_node(s_id, type="mirror", line="S", description=s_event)
                stats["nodes"] += 1

            self.G.add_edge(r_id, s_id, type="mirrors")
            stats["edges"] += 1

    def _sync_values(self, text: str, stats: dict) -> None:
        match = re.search(r"^## 已確立的數值設定", text, re.MULTILINE)
        if not match:
            return
        rest = text[match.end():]
        next_h = re.search(r"^## ", rest, re.MULTILINE)
        section = rest[:next_h.start()] if next_h else rest

        for line in section.strip().split("\n"):
            if not line.startswith("|") or line.startswith("|-"):
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 4 or cells[1] == "設定":
                continue

            setting = cells[1]
            value = cells[2]
            note = cells[3] if len(cells) > 3 else ""

            val_id = f"value:{setting}"
            self.G.add_node(val_id, type="value", setting=setting, value=value, note=note)
            stats["nodes"] += 1

            for ch_num in _parse_nums(note):
                ch_id = f"chapter:ch{ch_num}"
                if not self.G.has_node(ch_id):
                    self.G.add_node(ch_id, type="chapter", number=ch_num)
                    stats["nodes"] += 1
                self.G.add_edge(val_id, ch_id, type="established_in")
                stats["edges"] += 1

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
                ancestors = nx.ancestors(self.G.subgraph(
                    [n for n in self.G.nodes if self.G.nodes[n].get("type") == "event"]
                ), node)
                for a in ancestors:
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


def _parse_nums(text: str) -> list[int]:
    """Extract numbers from text like 'ch2,ch4' or '1,3,5'."""
    return [int(n) for n in re.findall(r"\d+", text)]
