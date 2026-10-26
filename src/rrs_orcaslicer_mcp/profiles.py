"""Resolve profile inheritance explicitly and report ambiguous vendor/profile names."""

from .storage import Files


def listing(
    files: Files, directory: str, query: str = "", offset: int = 0, limit: int = 50
) -> dict:
    root = files.path(directory)
    if not root.is_dir():
        raise ValueError("Profile directory does not exist")
    matches = []
    for path in sorted(root.rglob("*.json")):
        try:
            data = files.read(str(path))
            setting = data["settings"]
            row = {
                "path": str(path),
                "name": setting.get("name", path.stem),
                "type": setting.get("type"),
                "inherits": setting.get("inherits"),
                "sha256": data["sha256"],
            }
            if query.lower() in str(row).lower():
                matches.append(row)
        except (ValueError, OSError):
            continue
    return {
        "total": len(matches),
        "profiles": matches[max(0, offset) : max(0, offset) + max(1, min(limit, 200))],
    }


def resolve(files: Files, name: str, directories: list[str]) -> dict:
    index: dict[str, list[str]] = {}
    for directory in directories:
        root = files.path(directory)
        for path in root.rglob("*.json"):
            try:
                value = files.read(str(path))["settings"]
                key = value.get("name", path.stem)
                if str(path) not in index.setdefault(key, []):
                    index[key].append(str(path))
            except (ValueError, OSError):
                continue
    chain = []
    active = set()

    def visit(path: str) -> dict:
        canonical = str(files.path(path, True))
        if canonical in active or len(active) >= 100:
            raise ValueError("Cyclic or excessive profile inheritance")
        active.add(canonical)
        value = files.read(canonical)["settings"]
        result = {}
        if parent := value.get("inherits"):
            candidates = index.get(parent, [])
            if len(candidates) != 1:
                raise ValueError(f"Parent {parent!r} is missing or ambiguous: {candidates}")
            result.update(visit(candidates[0]))
        result.update(value)
        chain.append(canonical)
        active.remove(canonical)
        return result

    return {
        "settings": visit(name),
        "chain": chain,
        "notice": "JSON inheritance merge; OrcaSlicer performs schema migration and final validation.",
    }
