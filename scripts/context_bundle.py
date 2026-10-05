"""Provider-neutral, provenance-bearing context assembled under an exact character budget.

Blocks are atomic: callers decide the smallest complete statement that can safely
be omitted. This module neither summarizes nor truncates them, reads no sources,
and makes no token-count claim. Priority controls selection, not truth or authority.
"""

from dataclasses import dataclass, replace
from typing import Iterable, Literal


Section = Literal["author_intent", "canon_as_of", "pov_knowledge", "continuity", "reference"]
SECTION_TITLES: dict[Section, str] = {
    "author_intent": "作者意圖／規劃（不是已發生事實）",
    "canon_as_of": "截至章前的已記錄事實（不是後續情節）",
    "pov_knowledge": "視角角色的所知／信念（不等於客觀事實）",
    "continuity": "接續線索與敘事連貫",
    "reference": "參考材料（須依來源判讀）",
}


@dataclass(frozen=True)
class SourceRef:
    """A caller-verified source span; this module does not verify its contents."""

    path: str
    start_line: int
    end_line: int
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("Source path must be a nonempty string")
        if "\n" in self.path or "\r" in self.path:
            raise ValueError("Source path must fit on one line")
        if (type(self.start_line) is not int or type(self.end_line) is not int
                or self.start_line < 1 or self.end_line < self.start_line):
            raise ValueError("Source lines must be positive integers with end_line >= start_line")
        if self.sha256 is not None and (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in self.sha256)
        ):
            raise ValueError("Source sha256 must be a 64-character hexadecimal digest")

    def as_dict(self) -> dict[str, str | int]:
        result: dict[str, str | int] = {
            "path": self.path, "start_line": self.start_line, "end_line": self.end_line,
        }
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True)
class ContextBlock:
    """One indivisible statement or coherent unit of context.

    Higher numeric priority is more relevant among optional blocks. Required
    blocks always precede optional blocks within their section. Sources may be
    absent for user instructions or other context without a file-backed origin.
    """

    key: str
    section: Section
    text: str
    required: bool = False
    priority: int = 0
    sources: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("Block key must be a nonempty string")
        if "\n" in self.key or "\r" in self.key:
            raise ValueError("Block key must fit on one line")
        if self.section not in SECTION_TITLES:
            raise ValueError(f"Unknown context section: {self.section!r}")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Block text must be a nonempty string")
        if type(self.required) is not bool or type(self.priority) is not int:
            raise ValueError("Block required must be bool and priority must be int")
        sources = tuple(self.sources)
        if any(not isinstance(source, SourceRef) for source in sources):
            raise ValueError("Block sources must contain SourceRef instances")
        object.__setattr__(self, "sources", sources)


@dataclass(frozen=True)
class ContextBundle:
    text: str
    metadata: dict[str, object]


def _ordered(blocks: list[ContextBlock]) -> list[ContextBlock]:
    return [block for section in SECTION_TITLES for block in blocks if block.section == section]


def _render(blocks: list[ContextBlock], title: str, footer: str) -> str:
    parts = [f"# {title}"] if title else []
    for section, heading in SECTION_TITLES.items():
        section_blocks = [block for block in blocks if block.section == section]
        if not section_blocks:
            continue
        parts.append(f"## {heading}")
        for block in section_blocks:
            body = f"[{block.key}]\n{block.text}"
            if block.sources:
                sources = []
                for source in dict.fromkeys(block.sources):
                    location = f"{source.path}:{source.start_line}-{source.end_line}"
                    digest = f" (sha256:{source.sha256})" if source.sha256 else ""
                    sources.append(f"- 來源：{location}{digest}")
                body += "\n" + "\n".join(sources)
            parts.append(body)
    if footer:
        parts.append(footer)
    return "\n\n".join(parts)


def build_context_bundle(
    blocks: Iterable[ContextBlock], *, max_chars: int,
    title: str = "Chapter context", footer: str = "",
) -> ContextBundle:
    """Select complete blocks and return text plus bounded-selection metadata.

    ``max_chars`` bounds ``len(bundle.text)`` (Unicode code points), including
    title, section headings, keys, citations, separators and footer. Metadata is
    separate and not part of this text budget. All required blocks must fit or
    ValueError is raised. Optional blocks use descending priority and stable
    input order; an oversized candidate is skipped, not allowed to block later
    smaller candidates. This is a priority-greedy selector, not a knapsack solver.

    Duplicate keys keep the first payload. Identical payloads merge the strongest
    required/priority settings; conflicting payloads raise if either is required.
    Each duplicate input is reported as omitted, without copying its content.
    """
    if type(max_chars) is not int or max_chars < 0:
        raise ValueError("max_chars must be a nonnegative integer")
    if not isinstance(title, str) or not isinstance(footer, str):
        raise ValueError("title and footer must be strings")

    unique: dict[str, ContextBlock] = {}
    conflicting_keys: set[str] = set()
    omitted: list[dict[str, object]] = []
    input_count = 0
    for block in blocks:
        input_count += 1
        if not isinstance(block, ContextBlock):
            raise ValueError("blocks must contain ContextBlock instances")
        previous = unique.get(block.key)
        if previous is None:
            unique[block.key] = block
            continue
        same_payload = (previous.section, previous.text, previous.sources) == (
            block.section, block.text, block.sources,
        )
        if (previous.required or block.required) and (
            not same_payload or block.key in conflicting_keys
        ):
            raise ValueError(f"Conflicting required duplicate block: {block.key}")
        if not same_payload:
            conflicting_keys.add(block.key)
        if same_payload:
            unique[block.key] = replace(
                previous, required=previous.required or block.required,
                priority=max(previous.priority, block.priority),
            )
        omitted.append({"key": block.key, "section": block.section, "reason": "duplicate_key"})

    selected = [block for block in unique.values() if block.required]
    required_chars = len(_render(selected, title, footer))
    if required_chars > max_chars:
        raise ValueError(
            f"Required context needs {required_chars} characters; max_chars is {max_chars}. "
            "Required blocks, headings and footer cannot be truncated."
        )

    optional = sorted(
        (block for block in unique.values() if not block.required),
        key=lambda block: -block.priority,
    )
    for block in optional:
        if len(_render(selected + [block], title, footer)) <= max_chars:
            selected.append(block)
        else:
            omitted.append({
                "key": block.key, "section": block.section, "reason": "char_budget",
            })

    selected = _ordered(selected)
    rendered = _render(selected, title, footer)
    included = [{
        "key": block.key, "section": block.section,
        "required": block.required, "priority": block.priority,
        "sources": [source.as_dict() for source in dict.fromkeys(block.sources)],
    } for block in selected]
    included_sources = list(dict.fromkeys(source for block in selected for source in block.sources))
    metadata: dict[str, object] = {
        "budget_unit": "characters", "char_count": len(rendered), "max_chars": max_chars,
        "input_count": input_count, "included_count": len(selected),
        "omitted_count": len(omitted), "included": included, "omitted": omitted,
        "sources": [source.as_dict() for source in included_sources],
        "omitted_sources": {
            row["key"]: [source.as_dict() for source in unique[row["key"]].sources]
            for row in omitted if row["reason"] == "char_budget"
        },
    }
    return ContextBundle(text=rendered, metadata=metadata)


def format_context_diagnostics(metadata: dict, *, max_chars: int = 2400,
                               max_items: int = 20) -> str:
    """Bounded navigation-only appendix for the text CLI, outside bundle.text.

    Do not re-expose omitted prose, invalid records or whole-graph references.
    JSON carries the complete diagnostic lists when the bounded preview is short.
    """
    if type(max_chars) is not int or max_chars < 400:
        raise ValueError("diagnostic max_chars must be an integer >= 400")
    if type(max_items) is not int or max_items < 1:
        raise ValueError("diagnostic max_items must be a positive integer")
    rows = [*metadata.get("omitted", []), *metadata.get("narrative_excluded", []),
            *metadata.get("graph_excluded", [])]
    if not rows:
        return ""
    sources = metadata.get("omitted_sources", {})
    header = ("## CONTEXT DIAGNOSTICS / 未注入項目（導航，不是正文證據）\n"
              f"共 {len(rows)} 筆省略／排除；本診斷附錄另計篇幅，最多 {max_chars} 字元。")

    def footer(shown):
        return (f"\n顯示 {shown}/{len(rows)} 筆；完整 ID／原因／來源在 --format json 的 context_metadata。"
                "\nchar_budget 可按所列行段補讀並核對來源；retired／stale／needs_review／wrong_pov 不可當有效知情補回。"
                "\n沒有安全來源定位時請主 Agent 做指定 ID 的局部查找，不展開整份累積圖譜。")

    lines = []
    for row in rows[:max_items]:
        key = row.get("key", row.get("id", "unknown"))
        line = f"- {key} | {row.get('reason', 'unknown')}"
        if row.get("reason") == "char_budget":
            refs = sources.get(key, [])
            if refs:
                line += " | " + "; ".join(
                    f"{ref['path']}:{ref['start_line']}-{ref['end_line']}" for ref in refs
                )
            else:
                line += " | 無安全來源行段"
        candidate = header + "\n" + "\n".join([*lines, line]) + footer(len(lines) + 1)
        if len(candidate) > max_chars:
            break  # Never truncate an ID or citation into a different lookup.
        lines.append(line)
    return header + ("\n" + "\n".join(lines) if lines else "") + footer(len(lines))
