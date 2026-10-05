"""Foreshadow plan identities; compatibility aliases never rewrite graph keys."""

from __future__ import annotations

import re
import unicodedata


ACTIONS = {"plant", "hint", "resolve"}
_DIGITS = "零一二三四五六七八九"
_CN = "零〇一二三四五六七八九十百千萬万"
_CIRCLED = {chr(code): int(unicodedata.numeric(chr(code)))
            for start, end in ((0x2460, 0x2474), (0x3251, 0x3260), (0x32B1, 0x32C0))
            for code in range(start, end)}


def _number(text: str) -> int | None:
    if text.isdecimal():
        value = int(text)
        return value if value > 0 else None
    if not text or any(c not in _CN for c in text):
        return None
    text = text.replace("〇", "零").replace("万", "萬")
    if all(char in _DIGITS for char in text):
        value = int("".join(str(_DIGITS.index(char)) for char in text))
        return value if value > 0 else None
    total = section = digit = 0
    previous_digit, previous_unit = False, 10000
    for char in text:
        if char in _DIGITS:
            if previous_digit and digit:
                return None
            digit = _DIGITS.index(char)
            previous_digit = True
        elif char == "萬":
            if total or not section + digit:
                return None
            total += (section + digit) * 10000
            section = digit = 0
            previous_digit, previous_unit = False, 10000
        else:
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            if unit >= previous_unit:
                return None
            section += (digit or 1) * unit
            digit = 0
            previous_digit, previous_unit = False, unit
    value = total + section + digit
    return value if value > 0 else None


def legacy_thread_number(name: str) -> int | None:
    """Only explicit numbering syntax, never the numeral prefix of a title."""
    if not isinstance(name, str) or not name.strip():
        return None
    name = name.strip()
    if name[0] in _CIRCLED:
        return _CIRCLED[name[0]]
    circled = re.match(r"^伏筆\s*([①-⑳㉑-㉟㊱-㊿])", name)
    if circled:
        return _CIRCLED[circled.group(1)]
    match = re.match(rf"^伏筆\s*([0-9]+|[{_CN}]+)(?=$|[^0-9{_CN}])", name)
    if match:
        return _number(match.group(1))
    # A bare number is supported, but 三封未寄出的信 is an ordinary name.
    return _number(name)


def _canonical_legacy(value) -> str:
    if type(value) is int:
        if value < 1:
            raise ValueError("Foreshadow thread numbers must be positive")
        number = value
    else:
        value = _text(value, "thread")
        number = legacy_thread_number(value)
        numbered_tag = re.fullmatch(rf"(?:伏筆\s*)?(?:-?[0-9]+|[{_CN}]+)", value)
        if numbered_tag and number is None:
            raise ValueError("Legacy foreshadow numbers must be valid positive numbers")
        # Preserve named legacy graph keys; only standalone numbered tags normalize.
        if number is None or not (value.isdecimal() or all(c in _CN for c in value)
                                  or value in _CIRCLED
                                  or re.fullmatch(rf"伏筆\s*(?:[0-9]+|[{_CN}]+|[①-⑳㉑-㉟㊱-㊿])", value)):
            return value
    traditional = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二")
    return f"伏筆{traditional[number - 1] if number <= 12 else number}"


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"Foreshadow {label} must be nonempty single-line text")
    return value.strip()


def same_thread(first: str, second: str, *, explicit: bool = False) -> bool:
    if explicit:
        return first == second
    if first == second:
        return True
    number = legacy_thread_number(first)
    return number is not None and number == legacy_thread_number(second)


def resolve_thread(target: str, candidates, *, explicit: bool = False,
                   headings: bool = False) -> str | None:
    """Resolve at most one key; duplicate legacy aliases require human correction."""
    matches = []
    for candidate in candidates:
        key = candidate.split("｜", 1)[0].strip() if headings else candidate
        if same_thread(target, key, explicit=explicit):
            matches.append(candidate)
    if len(matches) > 1:
        raise ValueError(f"Ambiguous foreshadow identity {target!r}: {matches!r}")
    return matches[0] if matches else None


def _legacy_piece(piece: str) -> list[dict]:
    piece = piece.strip()
    if not piece or piece in {"-", "—", "無", "none", "None", "N/A"}:
        return []
    output, start = [], 0
    for match in re.finditer(r"(plant|hint|resolve)(?=$|\s|[①-⑳㉑-㉟㊱-㊿])", piece):
        prefix = piece[start:match.start()]
        identity = prefix.strip().rstrip(":：=").strip()
        # Named strings require an action delimiter. An English title such as
        # "eggplant" must not become thread="egg", action="plant".
        separated = bool(prefix and prefix[-1] in " \t:：=")
        numbered = (re.fullmatch(rf"(?:伏筆\s*)?(?:[0-9]+|[{_CN}]+|[①-⑳㉑-㉟㊱-㊿])", identity)
                    and legacy_thread_number(identity) is not None)
        if separated or numbered:
            if not identity:
                raise ValueError(f"Missing thread identity in foreshadow directive: {piece!r}")
            output.append({"thread_id": _canonical_legacy(identity),
                           "action": match.group(1), "legacy": True})
            start = match.end()
    if output:
        if piece[start:].strip():
            raise ValueError(f"Unparsed foreshadow directive: {piece!r}")
        return output
    # A numbered shorthand ending in an English verb is an attempted action,
    # not a new silently accepted title (e.g. ①plnat).
    if (re.search(r"[:：=]\s*[A-Za-z]+$", piece)
            or (legacy_thread_number(piece) is not None and re.search(r"[A-Za-z]+$", piece))
            or re.fullmatch(r"[0-9]+\s*[A-Za-z]+", piece)):
        raise ValueError(f"Unknown foreshadow action in {piece!r}; use plant, hint, or resolve")
    return [{"thread_id": _canonical_legacy(piece), "action": None, "legacy": True}]


def parse_legacy_directives(tag: str) -> list[dict]:
    if not isinstance(tag, str):
        raise ValueError("Legacy foreshadow tag must be text")
    pieces = re.split(r"[,，;；、/+＋]", tag)
    parsed = [directive for piece in pieces for directive in _legacy_piece(piece)]
    # Plain names (including punctuation or words such as "eggplant") remain
    # exact. Delimiters separate directives only when an action or an entirely
    # numbered legacy list makes that interpretation explicit.
    if (len(pieces) > 1 and not any(item["action"] for item in parsed)
            and not all(legacy_thread_number(piece.strip()) is not None for piece in pieces)):
        return _legacy_piece(tag)
    return parsed


def normalize_directives(items) -> list[dict]:
    """Normalize plan input while preserving actions and explicit opaque IDs."""
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("foreshadowing must be a list")
    output = []
    for item in items:
        if isinstance(item, str):
            output.extend(parse_legacy_directives(_text(item, "directive")))
            continue
        if not isinstance(item, dict) or set(item) - {"thread_id", "thread", "name", "action"}:
            raise ValueError("Foreshadow directives require thread_id (or legacy thread), name?, and action")
        if ("thread_id" in item) == ("thread" in item):
            raise ValueError("Use exactly one of thread_id or legacy thread")
        action = item.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("Foreshadow action must be plant, hint, or resolve")
        explicit = "thread_id" in item
        identity = (_text(item["thread_id"], "thread_id") if explicit
                    else _canonical_legacy(item["thread"]))
        directive = {"thread_id": identity, "action": action, "legacy": not explicit}
        if "name" in item:
            directive["name"] = _text(item["name"], "name")
        output.append(directive)
    return output


def directive_threads(directives: list[dict]) -> list[str]:
    return list(dict.fromkeys(item["thread_id"] for item in directives))
