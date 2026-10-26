"""Build the dependency-free official-host plugin from the reviewed source modules."""

from pathlib import Path
import ast
import sys


def standalone(source_text: str) -> str:
    lines = source_text.splitlines(keepends=True)
    imports = [
        node
        for node in ast.parse(source_text).body
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module in ("protocol", "service")
    ]
    for node in reversed(imports):
        del lines[node.lineno - 1 : node.end_lineno]
    return "".join(lines)


root = Path(__file__).resolve().parents[1]
source = root / "src/rrs_orcaslicer_mcp/host_bridge"
entry = standalone((source / "entry_template.py").read_text(encoding="utf-8"))
for marker, filename in (("PROTOCOL", "protocol.py"), ("SERVICE", "service.py")):
    content = (source / filename).read_text(encoding="utf-8")
    # Protocol helpers are included above the service in the standalone file.
    content = standalone(content)
    entry = entry.replace(f"# %%BRIDGE_{marker}%%", content)
entry = "# ruff: noqa: E402\n" + entry
compile(entry, "rrs_orcaslicer_bridge.py", "exec")
destination = root / "src/rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py"
if "--check" in sys.argv:
    if not destination.exists() or destination.read_text(encoding="utf-8") != entry:
        raise SystemExit("Host plugin is stale; run scripts/build_host_plugin.py")
    print("Host plugin matches reviewed source modules")
else:
    destination.write_text(entry, encoding="utf-8")
    print(f"Saved standalone host plugin: {destination}")
