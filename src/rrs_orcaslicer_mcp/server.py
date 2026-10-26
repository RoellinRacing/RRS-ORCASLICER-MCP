"""MCP entry point. No global executable runs or file writes on module import."""

import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from . import __version__, catalog, profiles, projects
from .desktop import Desktop
from .engine import Engine
from .storage import Files, atomic_json


def create_server() -> FastMCP:
    roots = [Path(x) for x in os.environ.get("ORCA_MCP_ROOTS", str(Path.cwd())).split(os.pathsep) if x]
    files = Files(roots)
    state = Path(os.environ.get("ORCA_MCP_STATE", str(Path.home() / ".rrs-orca"))).expanduser().resolve()
    desktop = Desktop()
    engine = None

    def backend() -> Engine:
        nonlocal engine
        if engine is None:
            engine = Engine(state / "jobs")
        return engine

    @asynccontextmanager
    async def lifespan(server):
        yield {}
        if engine:
            await engine.close()

    mcp = FastMCP("RRS OrcaSlicer MCP", instructions="Use orca_capabilities first. CLI flags come from installed --help. Read SHA256 before edits. Use absolute paths in CLI arguments because jobs have their own working directory. GUI-only workflows require the optional local desktop adapter and screenshots. Never claim a print was started from successful slicing alone.", lifespan=lifespan)

    @mcp.tool()
    async def orca_capabilities(refresh: bool = False) -> dict[str, Any]:
        """Detect installed CLI flags, version/help text and desktop availability."""
        return {"server_version": __version__, "cli": await backend().capabilities(refresh), "desktop": desktop.status(), "roots": [str(p) for p in files.roots], "source_catalog": catalog.snapshot()["upstream"]}

    @mcp.tool()
    def settings_catalog(query: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
        """Search source-derived setting names, types, labels, enums and ranges (hints)."""
        return catalog.search(query, offset, limit)

    @mcp.tool()
    def settings_read(path: str) -> dict[str, Any]:
        """Read any JSON profile or Orca preferences file with revision SHA256."""
        return files.read(path)

    @mcp.tool()
    def workspace_list(directory: str = ".", offset: int = 0, limit: int = 100) -> dict[str, Any]:
        """List local models, generated artifacts and profile folders within configured roots."""
        path = files.path(directory)
        if not path.is_dir():
            raise ValueError("Directory does not exist")
        entries = sorted(path.iterdir())
        return {"directory": str(path), "total": len(entries), "entries": [{"name": p.name, "directory": p.is_dir(), "size": p.stat().st_size if p.is_file() else None} for p in entries[max(0, offset):max(0, offset) + max(1, min(limit, 200))]]}

    @mcp.tool()
    def artifact_read(path: str, offset_bytes: int = 0, limit_bytes: int = 16000) -> dict[str, Any]:
        """Read a bounded chunk of generated G-code, JSON statistics or logs as text."""
        target = files.path(path, True)
        with target.open("rb") as stream:
            stream.seek(max(0, offset_bytes))
            content = stream.read(max(1, min(limit_bytes, 100000)))
        return {"path": str(target), "size": target.stat().st_size, "offset": max(0, offset_bytes), "text": content.decode("utf-8", errors="replace")}

    @mcp.tool()
    def settings_write(path: str, changes: dict, expected_sha256: str | None = None, remove: list[str] | None = None) -> dict[str, Any]:
        """Create/merge arbitrary settings, preserving unknown keys; backup existing files.

        Existing files require current expected_sha256. Keep Orca's serialized value
        representation, commonly strings and lists of strings. Close Orca before
        editing live user profiles, or save a new profile and import it in the GUI.
        """
        return files.write(path, changes, remove or [], expected_sha256)

    @mcp.tool()
    def profiles_list(directory: str, query: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
        """Discover printer, filament and process profiles below a configured root."""
        return profiles.listing(files, directory, query, offset, limit)

    @mcp.tool()
    def profile_resolve(path: str, search_directories: list[str]) -> dict[str, Any]:
        """Resolve inherited JSON values; reject cycles and ambiguous parent names."""
        return profiles.resolve(files, path, search_directories)

    @mcp.tool()
    def project_inspect(path: str, metadata_member: str = projects.SETTINGS) -> dict[str, Any]:
        """List 3MF members and read JSON/text metadata, including per-object XML."""
        if not metadata_member.startswith("Metadata/"):
            raise ValueError("Only Metadata members can be read as text")
        return projects.inspect(files, path, metadata_member)

    @mcp.tool()
    def project_settings_write(source: str, destination: str, changes: dict, expected_source_sha256: str, remove: list[str] | None = None) -> dict[str, Any]:
        """Write project settings to a new 3MF; preserve meshes, painting and unknown members."""
        return projects.patch(files, source, destination, changes, expected_source_sha256, remove=remove)

    @mcp.tool()
    def project_metadata_write(source: str, destination: str, metadata_member: str, text: str, expected_source_sha256: str) -> dict[str, Any]:
        """Replace existing JSON/XML Metadata in a new 3MF, including object/plate settings.

        Read the original member first. This is an expert format-level operation;
        XML/JSON syntax is checked, but OrcaSlicer validates semantics when reopened.
        """
        return projects.patch(files, source, destination, {}, expected_source_sha256, metadata_member=metadata_member, metadata_text=text)

    @mcp.tool()
    async def cli_run(arguments: list[str], timeout_seconds: int = 3600) -> dict[str, Any]:
        """Queue any advertised long CLI flags with ordered raw argv (no shell).

        Supports all CLI actions in the installed version, not GUI-only functions.
        Inputs, profiles and outputs should use absolute paths. This trusted local
        tool runs Orca with your OS privileges; file-root checks do not sandbox CLI.
        """
        return await backend().submit(arguments, timeout_seconds)

    @mcp.tool()
    async def slice_project(inputs: list[str], output_directory: str, plate: int = 0, settings: list[str] | None = None, filaments: list[str] | None = None, export_3mf: str | None = None, timeout_seconds: int = 3600) -> dict[str, Any]:
        """Slice 3MF/STL/STEP inputs using the installed engine and supplied profiles.

        Plate 0 selects all plates. Use a self-contained Orca 3MF or supply complete
        printer/process/filament JSON; the bridge does not guess printer settings.
        """
        if not inputs or plate < 0:
            raise ValueError("Supply input files and plate >= 0")
        args = ["--slice", str(plate), "--outputdir", str(files.path(output_directory))]
        for flag, paths in (("--load-settings", settings), ("--load-filaments", filaments)):
            if paths:
                resolved = [str(files.path(p, True)) for p in paths]
                if any(";" in p for p in resolved):
                    raise ValueError("Orca CLI profile lists cannot represent semicolons in filenames")
                args += [flag, ";".join(resolved)]
        if export_3mf:
            args += ["--export-3mf", str(files.path(export_3mf))]
        args += [str(files.path(p, True)) for p in inputs]
        return await backend().submit(args, timeout_seconds)

    @mcp.tool()
    def job_status(job_id: str, log_tail_bytes: int = 8000) -> dict[str, Any]:
        """Read durable job state, output files and bounded log tail."""
        job = backend().get(job_id)
        log = Path(job["log"])
        if log.exists():
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - max(0, min(log_tail_bytes, 100000))))
                job["log_tail"] = stream.read().decode(errors="replace")
        job["files"] = [str(p) for p in Path(job["directory"]).rglob("*") if p.is_file()]
        return job

    @mcp.tool()
    def jobs_list(limit: int = 50) -> list[dict[str, Any]]:
        """List recent persisted jobs, including interrupted work after restarts."""
        paths = sorted(backend().state.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [backend().get(p.parent.name) for p in paths[:max(1, min(limit, 200))]]

    @mcp.tool()
    async def job_cancel(job_id: str) -> dict[str, Any]:
        """Cancel queued/running work and terminate its process tree."""
        return await backend().cancel(job_id)

    @mcp.tool()
    async def desktop_screenshot() -> Image:
        """Inspect foreground OrcaSlicer on the optional local desktop."""
        return Image(data=await asyncio.to_thread(desktop.screenshot), format="png")

    @mcp.tool()
    async def desktop_focus() -> dict[str, Any]:
        """Bring a single existing OrcaSlicer window to the foreground."""
        return await asyncio.to_thread(desktop.focus)

    @mcp.tool()
    async def desktop_launch(project: str | None = None) -> dict[str, Any]:
        """Launch the installed GUI, optionally opening a local project; requires desktop opt-in."""
        if not desktop.enabled:
            raise ValueError("Set ORCA_MCP_DESKTOP=1")
        if not backend().binary:
            raise ValueError("Set ORCA_SLICER_BIN")
        args = [backend().binary]
        if project:
            args.append(str(files.path(project, True)))
        import subprocess
        process = await asyncio.create_subprocess_exec(*args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"pid": process.pid, "launched": True, "next": "Wait for the window, focus it and inspect a screenshot"}

    @mcp.tool()
    async def desktop_action(action: str, x: int = 0, y: int = 0, text: str = "", keys: list[str] | None = None, amount: int = 0) -> dict[str, Any]:
        """Visual GUI interaction: click/double_click/right_click/move/drag/scroll/keys/text.

        Inspect screenshots before/after. Coordinates use the full desktop screenshot.
        OrcaSlicer must be foreground. Dialogs and permissions may need local handling.
        """
        return await asyncio.to_thread(desktop.action, action, x, y, text, keys, amount)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Standalone OrcaSlicer MCP (stdio)")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--doctor", action="store_true", help="Print CLI capabilities as JSON, then exit")
    parser.add_argument("--output", type=Path, help="Save doctor report as JSON")
    args = parser.parse_args()
    if args.doctor:
        import json
        engine = Engine(Path(os.environ.get("ORCA_MCP_STATE", str(Path.home() / ".rrs-orca"))) / "doctor")
        report = asyncio.run(engine.capabilities(True))
        if args.output:
            atomic_json(args.output, report)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["available"] else 1)
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
