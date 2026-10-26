"""Source snapshots are hints, never an invented API contract for an installed version."""

import json
import re
from importlib.resources import files


def strip_comments(source: str) -> str:
    # Keep quoted C++ strings intact, including comment-looking URLs.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: m[0] if m[0][0] in "\"'" else "\n" * m[0].count("\n"), source)


def extract(source: str) -> dict:
    clean = strip_comments(source)
    pattern = r'(?:this->)?add\("([^"\n]+)",\s*(co\w+)\)'
    matches = list(re.finditer(pattern, clean))
    options = {}
    for i, match in enumerate(matches):
        block = clean[match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(clean)]
        key, kind = match.groups()
        item = {
            "key": key,
            "type": kind,
            "source_line": clean.count("\n", 0, match.start()) + 1,
        }
        for field in ("label", "tooltip", "category", "cli", "cli_params"):
            found = re.search(
                r"def->" + field + r'\s*=\s*(?:\w+\()?((?:"(?:\\.|[^"\\])*"\s*)+)', block
            )
            if found:
                parts = re.findall(r'"((?:\\.|[^"\\])*)"', found[1])
                item[field] = "".join(parts).replace(r"\n", "\n").replace(r"\"", '"')
        for field in ("min", "max"):
            found = re.search(r"def->" + field + r"\s*=\s*(-?[\d.]+)\s*;", block)
            if found:
                item[field] = float(found[1])
        enums = re.findall(r'def->enum_values.push_back\("([^"]*)"\)', block)
        if enums:
            item["enum_values"] = enums
        options[key] = item
    return options


def snapshot() -> dict:
    return json.loads(files("rrs_orcaslicer_mcp").joinpath("data/options.json").read_text())


def search(query: str = "", offset: int = 0, limit: int = 50) -> dict:
    data = snapshot()
    options = [v for v in data["options"].values() if query.lower() in json.dumps(v).lower()]
    return {
        "upstream": data["upstream"],
        "total": len(options),
        "options": options[max(0, offset) : max(0, offset) + min(200, max(1, limit))],
        "notice": "Source-derived hints; installed OrcaSlicer validates actual settings. Unknown keys are preserved.",
    }
