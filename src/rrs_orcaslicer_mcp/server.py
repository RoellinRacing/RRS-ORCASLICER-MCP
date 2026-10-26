"""MCP entry point. No global executable runs or file writes on module import."""

import argparse
import asyncio
import os
import hashlib
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP, Image

from . import (
    __version__,
    catalog,
    calibration,
    meshes,
    profiles,
    projects,
    settings as profile_settings,
    project_settings,
    project_geometry,
    gcode,
)
from .native_workflows import NativeWorkflows, CALIBRATIONS
from .printers import Printers
from .batches import Batches
from .desktop import Desktop
from .engine import Engine
from .storage import Files, atomic_json, digest
from .host_bridge.client import HostClient


def create_server() -> FastMCP:
    roots = [
        Path(x) for x in os.environ.get("ORCA_MCP_ROOTS", str(Path.cwd())).split(os.pathsep) if x
    ]
    files = Files(roots)
    state = (
        Path(os.environ.get("ORCA_MCP_STATE", str(Path.home() / ".rrs-orca")))
        .expanduser()
        .resolve()
    )
    printers = Printers(state / "printer-requests")
    desktop = Desktop()
    host_client = HostClient()
    native = NativeWorkflows(host_client, desktop, files, state / "native-requests")
    engine = None
    batch_store = None

    def backend() -> Engine:
        nonlocal engine
        if engine is None:
            engine = Engine(state / "jobs")
        return engine

    def batches() -> Batches:
        nonlocal batch_store
        if batch_store is None:
            batch_store = Batches(state / "batches", backend())
        return batch_store

    @asynccontextmanager
    async def lifespan(server):
        try:
            yield {}
        finally:
            # Client disconnect may cancel the MCP task group. Shield cleanup so
            # process termination and the final job checkpoint still complete.
            with anyio.CancelScope(shield=True):
                if engine:
                    await engine.close()

    mcp = FastMCP(
        "RRS OrcaSlicer MCP",
        instructions="Use orca_capabilities first. CLI flags come from installed --help. Read SHA256 before edits. Use absolute paths in CLI arguments because jobs have their own working directory. GUI-only workflows require the optional local desktop adapter and screenshots. Never claim a print was started from successful slicing alone.",
        lifespan=lifespan,
    )

    @mcp.tool()
    async def orca_capabilities(refresh: bool = False) -> dict[str, Any]:
        """Detect installed CLI flags, version/help text and desktop availability."""
        return {
            "server_version": __version__,
            "cli": await backend().capabilities(refresh),
            "desktop": desktop.status(),
            "roots": [str(p) for p in files.roots],
            "source_catalog": catalog.snapshot()["upstream"],
        }

    @mcp.tool()
    def settings_catalog(query: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
        """Search source-derived setting names, types, labels, enums and ranges (hints)."""
        return catalog.search(query, offset, limit)

    @mcp.tool()
    async def feature_coverage() -> dict[str, Any]:
        """Report supported feature families and explicit GUI/API gaps without claiming 100%."""
        import json
        from importlib.resources import files as resources

        report = json.loads(
            resources("rrs_orcaslicer_mcp")
            .joinpath("data/coverage.json")
            .read_text(encoding="utf-8")
        )
        report["installed_cli"] = await backend().capabilities()
        report["live_host"] = host_client.status()
        return report

    @mcp.tool()
    def native_ui_capabilities() -> dict[str, Any]:
        """Inspect opt-in native workflow routes and their platform/locale/scene limits."""
        return {
            "desktop": desktop.status(),
            "bridge": host_client.status(),
            "calibration_kinds": sorted(CALIBRATIONS),
            "method": "Orca native visible controls plus official-host readback; stock binary unchanged",
            "acceptance_scope": "English interface; GUI/native results require operation-level validation",
            "transform_scope": "one object/instance; other rotation axes zero for relative rotation",
            "physical_printing": False,
        }

    @mcp.tool()
    async def native_scene_read() -> dict[str, Any]:
        """Read copied live scene identities/poses/settings and an observed revision for typed GUI edits.

        Revision is not a full mesh-content hash. Requires the running official
        bridge plugin; no desktop input occurs.
        """
        return await native.scene()

    @mcp.tool()
    async def native_transform(
        kind: str, axis: str, value: float, expected_revision: str, session_id: str, request_id: str
    ) -> dict[str, Any]:
        """Edit Orca's live native gizmo and verify actual model pose; native Undo is retained.

        kind move: value is relative millimeters; rotate: relative degrees; scale:
        target percent on the chosen x/y/z control (Orca's current uniform lock applies).
        Requires one object/instance, English mm UI and foreground Prepare mainframe.
        Opt in with ORCA_MCP_DESKTOP=1 and install [desktop] plus system Tesseract.
        Read native_scene_read and host_bridge_status first. Request IDs are 32 hex.
        """
        return await native.run(
            "transform",
            {"kind": kind, "axis": axis, "value": value},
            session_id,
            request_id,
            expected_revision,
        )

    @mcp.tool()
    async def native_history(
        direction: str, expected_revision: str, session_id: str, request_id: str, steps: int = 1
    ) -> dict[str, Any]:
        """Apply actual Orca undo/redo, 1..20 explicit native history steps, and read the result.

        Operates on Orca's native history, including manual edits. A workflow may
        create multiple native steps. No file-level pseudo-undo or automatic retries.
        Requires the foreground Prepare mainframe and a fresh observed scene revision.
        """
        return await native.run(
            "history",
            {"direction": direction, "steps": steps},
            session_id,
            request_id,
            expected_revision,
        )

    @mcp.tool()
    async def native_text(
        text: str,
        height_mm: float,
        depth_mm: float,
        mode: str,
        backup: str,
        destination: str,
        expected_revision: str,
        session_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Use Orca's editable native text/emboss tool: join, cut (engrave) or modifier.

        Requires one object/instance and foreground English Prepare UI. Saves the
        unsaved project to backup first. Both paths must be new .3mf files inside
        configured client/host export roots. Exports and verifies editable native
        text metadata, height and depth; this is not a faceted text STL substitute.
        """
        return await native.run(
            "text",
            {
                "text": text,
                "height_mm": height_mm,
                "depth_mm": depth_mm,
                "mode": mode,
                "backup": backup,
                "destination": destination,
            },
            session_id,
            request_id,
            expected_revision,
        )

    @mcp.tool()
    async def native_calibration(
        kind: str,
        values: dict[str, Any],
        backup: str,
        destination: str,
        expected_revision: str,
        session_id: str,
        request_id: str,
        replace_scene: bool = False,
    ) -> dict[str, Any]:
        """Invoke Orca's actual native calibration generator, not independent coupon sweeps.

        kind temperature (start/end, native fixed 5 C steps), pressure_advance
        (start/end/step, method tower/line/pattern), max_volumetric_speed, retraction,
        vfa (start/end/step), cornering (start/end), flow_ratio (test pass_1/pass_2/yolo/
        yolo_perfectionist), input_shaping_frequency (x_start/x_end/y_start/y_end),
        input_shaping_damping (freq_x/freq_y/start/end). Firmware-specific dialogs
        must match visible expected controls. Back up unsaved project and explicitly
        replace_scene=true; export generated native 3MF. Never starts a print.
        """
        return await native.run(
            "calibration",
            {
                "kind": kind,
                "values": values,
                "backup": backup,
                "destination": destination,
                "replace_scene": replace_scene,
            },
            session_id,
            request_id,
            expected_revision,
        )

    @mcp.tool()
    def native_request_status(request_id: str) -> dict[str, Any]:
        """Read persistent typed native GUI receipt and screenshot/backup paths without repeating input."""
        return native.result(request_id)

    @mcp.tool()
    def printer_capabilities() -> dict[str, Any]:
        """List explicit configured Moonraker/OctoPrint hosts. Configure ORCA_MCP_PRINTERS JSON."""
        return printers.capabilities()

    @mcp.tool()
    async def printer_status(printer_id: str) -> dict[str, Any]:
        """Query actual configured printer/job state without issuing machine commands."""
        return await printers.status(printer_id)

    @mcp.tool()
    async def printer_upload(
        printer_id: str, source: str, remote_name: str, expected_source_sha256: str, request_id: str
    ) -> dict[str, Any]:
        """Upload checksum-bound text G-code without starting it. request_id is 32 hex digits.

        The provider may replace an existing remote filename. Use a unique name.
        A repeated request ID returns its receipt; uncertain dispatch is never retried.
        """
        return await printers.dispatch(
            printer_id, request_id, "upload", remote_name, files, source, expected_source_sha256
        )

    @mcp.tool()
    async def printer_command(
        printer_id: str, action: str, request_id: str, remote_name: str | None = None
    ) -> dict[str, Any]:
        """Send an explicit physical printer command: start/pause/resume/cancel.

        start requires an uploaded remote_name; upload never starts a print.
        Use a fresh 32-hex request_id only for a new authorized action. Reuse it
        to retrieve acknowledgement after interruption. Query actual state afterward.
        """
        return await printers.dispatch(printer_id, request_id, action, remote_name)

    @mcp.tool()
    def printer_request_status(request_id: str) -> dict[str, Any]:
        """Retrieve durable printer dispatch receipt without repeating the command."""
        return printers.result(request_id)

    @mcp.tool()
    def host_bridge_status() -> dict[str, Any]:
        """Inspect the running official-host plugin, session ID and advertised operations."""
        return host_client.status()

    @mcp.tool()
    def host_plugin_export(destination: str) -> dict[str, Any]:
        """Write the standalone official-host plugin to a new file for local installation."""
        from importlib.resources import files as resources

        target = files.path(destination)
        if target.exists() or target.suffix != ".py":
            raise ValueError("Choose a new .py destination")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(
                resources("rrs_orcaslicer_mcp")
                .joinpath("data/rrs_orcaslicer_bridge.py")
                .read_bytes()
            )
        return {
            "path": str(target),
            "sha256": digest(target),
            "next": "Install local plugin in a compatible Orca nightly, then Plugins > Run. Set ORCA_MCP_BRIDGE to the path shown by its panel.",
        }

    @mcp.tool()
    async def host_snapshot() -> dict[str, Any]:
        """Read live app version, dirty states, selected presets and scene object count."""
        return await host_client.call("host.snapshot", {})

    @mcp.tool()
    async def host_model_read(offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """Read live objects, IDs, parts/instance counts and existing painting flags."""
        return await host_client.call("model.read", {"offset": offset, "limit": limit})

    @mcp.tool()
    async def host_model_detail(
        index: int, object_id: int, offset: int = 0, limit: int = 20
    ) -> dict[str, Any]:
        """Read volumes, types, poses, material slots and instances for a known live object ID.

        Use host_model_read first. Rotations are radians and offsets millimeters.
        Values are copied on the GUI thread; no native handles leave the callback.
        """
        return await host_client.call(
            "model.detail",
            {"index": index, "object_id": object_id, "offset": offset, "limit": limit},
        )

    @mcp.tool()
    async def host_printer_read() -> dict[str, Any]:
        """Read selected printer agent/link/online/firmware if exposed. No credentials or commands."""
        return await host_client.call("printer.read", {})

    @mcp.tool()
    async def host_slicing_events(after: int = 0, limit: int = 100) -> dict[str, Any]:
        """Read bounded native pipeline events after a sequence cursor, including dropped-event gaps.

        Select RRS MCP slicing observer in the process preset slicing_pipeline_plugin
        first. Compare epoch on reload. Events describe stages, not progress percentage.
        """
        return await host_client.call("slicing.events", {"after": after, "limit": limit})

    @mcp.tool()
    async def host_presets_list(
        kind: str, query: str = "", offset: int = 0, limit: int = 100
    ) -> dict[str, Any]:
        """List the running host's loaded process, printer or filament presets."""
        return await host_client.call(
            "presets.list", {"kind": kind, "query": query, "offset": offset, "limit": limit}
        )

    @mcp.tool()
    async def host_preset_read(
        kind: str,
        name: str | None = None,
        keys: list[str] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Read serialized live preset values, including unsaved edits; redact secret keys."""
        return await host_client.call(
            "preset.read",
            {"kind": kind, "name": name, "keys": keys, "offset": offset, "limit": limit},
        )

    @mcp.tool()
    async def host_preset_update(
        kind: str,
        preset_name: str,
        changes: dict,
        session_id: str,
        request_id: str,
        slot: int | None = None,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        """Stage/commit live settings through the official host transaction API.

        Requires the current session ID and an explicit UUID hex request ID. Changes
        stay unsaved. Native selection/unsaved-edit dialogs are never suppressed.
        A timeout is indeterminate: query the receipt instead of repeating the edit.
        """
        return await host_client.call(
            "preset.update",
            {"kind": kind, "preset_name": preset_name, "changes": changes, "slot": slot},
            timeout_seconds,
            session_id,
            request_id,
        )

    @mcp.tool()
    async def host_project_export(
        destination: str, session_id: str, request_id: str, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        """Export the live project with unsaved settings as a new 3MF copy.

        Destination must be in ORCA_MCP_ROOTS and the plugin's export_roots. Does not
        change the project's saved filename/state. Existing destinations are rejected.
        """
        path = files.path(destination)
        # A repeated successful request must remain eligible for its cached receipt.
        return await host_client.call(
            "project.export", {"destination": str(path)}, timeout_seconds, session_id, request_id
        )

    @mcp.tool()
    def host_request_status(session_id: str, request_id: str) -> dict[str, Any]:
        """Read an execution receipt, including after a client timeout or host restart."""
        return host_client.result(session_id, request_id)

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
        return {
            "directory": str(path),
            "total": len(entries),
            "entries": [
                {
                    "name": p.name,
                    "directory": p.is_dir(),
                    "size": p.stat().st_size if p.is_file() else None,
                }
                for p in entries[max(0, offset) : max(0, offset) + max(1, min(limit, 200))]
            ],
        }

    @mcp.tool()
    def artifact_read(path: str, offset_bytes: int = 0, limit_bytes: int = 16000) -> dict[str, Any]:
        """Read a bounded chunk of generated G-code, JSON statistics or logs as text."""
        target = files.path(path, True)
        with target.open("rb") as stream:
            stream.seek(max(0, offset_bytes))
            content = stream.read(max(1, min(limit_bytes, 100000)))
        return {
            "path": str(target),
            "size": target.stat().st_size,
            "offset": max(0, offset_bytes),
            "text": content.decode("utf-8", errors="replace"),
        }

    @mcp.tool()
    def settings_write(
        path: str,
        changes: dict,
        expected_sha256: str | None = None,
        remove: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create/merge arbitrary settings, preserving unknown keys; backup existing files.

        Existing files require current expected_sha256. Keep Orca's serialized value
        representation, commonly strings and lists of strings. Close Orca before
        editing live user profiles, or save a new profile and import it in the GUI.
        """
        return files.write(path, changes, remove or [], expected_sha256)

    @mcp.tool()
    def profiles_list(
        directory: str, query: str = "", offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        """Discover printer, filament and process profiles below a configured root."""
        return profiles.listing(files, directory, query, offset, limit)

    @mcp.tool()
    def profile_resolve(path: str, search_directories: list[str]) -> dict[str, Any]:
        """Resolve inherited JSON values; reject cycles and ambiguous parent names."""
        return profiles.resolve(files, path, search_directories)

    @mcp.tool()
    def settings_compare(left_path: str, right_path: str) -> dict[str, Any]:
        """Compare serialized profiles exactly; report added, removed and changed keys."""
        left, right = files.read(left_path), files.read(right_path)
        return {
            "left_sha256": left["sha256"],
            "right_sha256": right["sha256"],
            **profile_settings.compare(left["settings"], right["settings"]),
        }

    @mcp.tool()
    def settings_validate(values: dict) -> dict[str, Any]:
        """Advisory check of source-known types, ranges and enums; not engine validation."""
        return profile_settings.validate(values)

    @mcp.tool()
    def profile_export(
        source: str,
        destination: str,
        name: str,
        search_directories: list[str],
        profile_version: str | None = None,
    ) -> dict[str, Any]:
        """Create a new flattened user profile with inherited values and no parent dependency."""
        return profile_settings.export_profile(
            files, source, destination, name, search_directories, profile_version
        )

    @mcp.tool()
    def project_inspect(path: str, metadata_member: str = projects.SETTINGS) -> dict[str, Any]:
        """List 3MF members and read JSON/text metadata, including per-object XML."""
        if not metadata_member.startswith("Metadata/"):
            raise ValueError("Only Metadata members can be read as text")
        return projects.inspect(files, path, metadata_member)

    @mcp.tool()
    def project_settings_write(
        source: str,
        destination: str,
        changes: dict,
        expected_source_sha256: str,
        remove: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write project settings to a new 3MF; preserve meshes, painting and unknown members."""
        return projects.patch(
            files, source, destination, changes, expected_source_sha256, remove=remove
        )

    @mcp.tool()
    def project_metadata_write(
        source: str, destination: str, metadata_member: str, text: str, expected_source_sha256: str
    ) -> dict[str, Any]:
        """Replace existing JSON/XML Metadata in a new 3MF, including object/plate settings.

        Read the original member first. This is an expert format-level operation;
        XML/JSON syntax is checked, but OrcaSlicer validates semantics when reopened.
        """
        return projects.patch(
            files,
            source,
            destination,
            {},
            expected_source_sha256,
            metadata_member=metadata_member,
            metadata_text=text,
        )

    @mcp.tool()
    def mesh_inspect(source: str, expected_source_sha256: str) -> dict[str, Any]:
        """Measure an STL/PLY: bounds, volume, triangles, watertightness. Needs [geometry]."""
        return meshes.inspect(files, source, expected_source_sha256)

    @mcp.tool()
    def mesh_operation(
        sources: list[dict[str, str]],
        destination_directory: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Offline mesh repair/split/cut/merge/union/difference/intersection/hull/simplify/transform.

        sources: [{path,sha256}]. action convex_hull for hull. cut takes origin/normal
        XYZ vectors and optional cap (true); simplify takes face_count; transform takes
        a 4x4 column-vector affine matrix. Inputs STL/PLY, outputs new STL files in a new
        directory with measured result/checkpoint. Requires [geometry]. STL units assumed
        millimeters. Reimport output into Orca; settings and facet painting do not transfer.
        """
        return meshes.operation(files, sources, destination_directory, action, parameters)

    @mcp.tool()
    def calibration_series_create(
        source: str,
        destination_directory: str,
        expected_source_sha256: str,
        kind: str,
        values: list[float],
        filament_slot: int = 1,
    ) -> dict[str, Any]:
        """Create resumable temperature/flow_ratio/pressure_advance/max_volumetric_speed coupons.

        Uses the supplied calibration model in a 3MF, one constant-setting project per
        value. Preserves other filament slots. PA is explicitly enabled for its slot.
        This does not generate Orca's native towers, select a winner or start a print.
        Use batch_slice on the completed paths. Inspect/measure coupons before applying
        a selected result to a profile with the existing settings/profile tools.
        """
        return calibration.series(
            files,
            source,
            destination_directory,
            expected_source_sha256,
            kind,
            values,
            filament_slot,
        )

    @mcp.tool()
    def project_geometry_read(
        path: str, member: str = "3D/3dmodel.model", offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        """Inspect mesh IDs, component references and build transforms in a 3MF member."""
        return project_geometry.inspect(files, path, member, offset, limit)

    @mcp.tool()
    def project_transform_write(
        source: str,
        destination: str,
        expected_source_sha256: str,
        matrix: list[float],
        target: str = "build",
        index: int = 0,
        object_id: str | None = None,
        member: str = "3D/3dmodel.model",
    ) -> dict[str, Any]:
        """Set a build/component affine transform in a NEW 3MF; original and painting survive.

        Matrix uses 3MF's 12-number row-vector order: 3x3 linear part then XYZ
        translation in model units. Component changes affect ALL referencing instances.
        Read project_geometry_read and source SHA first. Requires reslicing/reopening.
        """
        return project_geometry.set_transform(
            files,
            source,
            destination,
            expected_source_sha256,
            matrix,
            target,
            index,
            object_id,
            member,
        )

    @mcp.tool()
    def project_painting_read(
        source: str,
        object_id: str,
        member: str = "3D/3dmodel.model",
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Read triangle IDs, indices and support/seam/material/fuzzy paint trees."""
        return project_geometry.painting_read(files, source, object_id, member, offset, limit)

    @mcp.tool()
    def project_painting_write(
        source: str,
        destination: str,
        expected_source_sha256: str,
        object_id: str,
        kind: str,
        changes: list[dict[str, Any]],
        member: str = "3D/3dmodel.model",
    ) -> dict[str, Any]:
        """Paint explicit triangles in a NEW 3MF, preserving other channels and topology.

        kind: support/seam/material/fuzzy_skin. Each change has triangle (0-based)
        and either state (0 none, 1 enforcer, 2 blocker; material 1..16 filament slot),
        or mask (validated Orca hex subdivision tree; null clears channel).
        Inspect member/object IDs and SHA first. Affects all uses of that mesh.
        """
        return project_geometry.painting_write(
            files, source, destination, expected_source_sha256, object_id, kind, changes, member
        )

    @mcp.tool()
    def project_objects_read(path: str) -> dict[str, Any]:
        """Read objects, part IDs, plates and instance assignments as structured settings."""
        return project_settings.inspect(files, path)

    @mcp.tool()
    def project_target_settings_write(
        source: str,
        destination: str,
        target: str,
        target_id: str,
        changes: dict,
        expected_source_sha256: str,
        remove: list[str] | None = None,
        part_id: str | None = None,
    ) -> dict[str, Any]:
        """Set object/part or plate print settings in a new 3MF using stored IDs.

        target is object or plate. Values are Orca's serialized strings. Geometry,
        identity and cached G-code references are protected. Reslicing is required.
        """
        return project_settings.write(
            files,
            source,
            destination,
            target,
            target_id,
            changes,
            expected_source_sha256,
            remove,
            part_id,
        )

    @mcp.tool()
    def gcode_analyze(path: str) -> dict[str, Any]:
        """Summarize declared time/material/layers, selected settings and temperature commands."""
        return gcode.analyze(files, path)

    @mcp.tool()
    async def cli_run(arguments: list[str], timeout_seconds: int = 3600) -> dict[str, Any]:
        """Queue any advertised long CLI flags with ordered raw argv (no shell).

        Supports all CLI actions in the installed version, not GUI-only functions.
        Inputs, profiles and outputs should use absolute paths. This trusted local
        tool runs Orca with your OS privileges; file-root checks do not sandbox CLI.
        """
        return await backend().submit(arguments, timeout_seconds)

    @mcp.tool()
    async def slice_project(
        inputs: list[str],
        output_directory: str,
        plate: int = 0,
        settings: list[str] | None = None,
        filaments: list[str] | None = None,
        export_3mf: str | None = None,
        timeout_seconds: int = 3600,
    ) -> dict[str, Any]:
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
                    raise ValueError(
                        "Orca CLI profile lists cannot represent semicolons in filenames"
                    )
                args += [flag, ";".join(resolved)]
        if export_3mf:
            # Orca 2.4.2 concatenates outputdir + export-3mf literally, even for
            # absolute paths. Send a basename and keep exports in output_directory.
            export = Path(export_3mf)
            if export.is_absolute():
                if files.path(export_3mf).parent != files.path(output_directory):
                    raise ValueError("3MF export must be inside output_directory")
            elif export.name != export_3mf:
                raise ValueError(
                    "export_3mf must be a basename or absolute path in output_directory"
                )
            args += ["--export-3mf", export.name]
        args += [str(files.path(p, True)) for p in inputs]
        files.path(output_directory).mkdir(parents=True, exist_ok=True)
        return await backend().submit(args, timeout_seconds)

    @mcp.tool()
    async def batch_slice(
        inputs: list[str],
        output_directory: str,
        idempotency_key: str,
        plate: int = 0,
        settings: list[str] | None = None,
        filaments: list[str] | None = None,
        timeout_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Slice up to 64 inputs independently with durable, retry-safe batch identity.

        Reusing a key with unchanged inputs returns existing jobs; changed contents
        cause a conflict. Each input has its own output folder and sliced 3MF.
        Interrupted/failed work is never silently repeated; use a new key to retry it.
        """
        if not 1 <= len(inputs) <= 64 or plate < 0 or not 1 <= timeout_seconds <= 86400:
            raise ValueError("Supply 1..64 inputs, plate >= 0, timeout 1..86400")
        if not 1 <= len(idempotency_key) <= 200 or not idempotency_key.strip():
            raise ValueError("Supply an idempotency key of 1..200 characters")
        resolved_inputs = [str(files.path(p, True)) for p in inputs]
        base = files.path(output_directory)
        ident = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        common = ["--slice", str(plate)]
        profile_paths = []
        for flag, paths in (("--load-settings", settings), ("--load-filaments", filaments)):
            if paths:
                resolved = [str(files.path(p, True)) for p in paths]
                if any(";" in p for p in resolved):
                    raise ValueError("Profile filenames cannot contain semicolons")
                profile_paths += resolved
                common += [flag, ";".join(resolved)]
        checks = {
            p: digest(files.path(p, True)) for p in dict.fromkeys(resolved_inputs + profile_paths)
        }
        entries = []
        for index, path in enumerate(resolved_inputs):
            stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(path).stem)[:40]
            directory = base / ident / f"{index + 1:03d}-{stem}"
            args = common + ["--outputdir", str(directory), "--export-3mf", "sliced.3mf", path]
            entries.append(
                {
                    "input": path,
                    "output_directory": str(directory),
                    "arguments": args,
                    "expected_files": {p: checks[p] for p in dict.fromkeys([path] + profile_paths)},
                }
            )
        request = {
            "inputs": resolved_inputs,
            "output_directory": str(base),
            "plate": plate,
            "settings": common,
        }
        return await batches().create(idempotency_key, request, entries, timeout_seconds, checks)

    @mcp.tool()
    def batch_status(batch_id: str) -> dict[str, Any]:
        """Aggregate durable batch status and per-input job IDs after reconnecting."""
        return batches().get(batch_id)

    @mcp.tool()
    async def batch_cancel(batch_id: str) -> dict[str, Any]:
        """Cancel active/queued work in a batch and keep successful results unchanged."""
        return await batches().cancel(batch_id)

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
        paths = sorted(
            backend().state.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return [backend().get(p.parent.name) for p in paths[: max(1, min(limit, 200))]]

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

        process = await asyncio.create_subprocess_exec(
            *args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return {
            "pid": process.pid,
            "launched": True,
            "next": "Wait for the window, focus it and inspect a screenshot",
        }

    @mcp.tool()
    async def desktop_action(
        action: str,
        x: int = 0,
        y: int = 0,
        text: str = "",
        keys: list[str] | None = None,
        amount: int = 0,
    ) -> dict[str, Any]:
        """Visual GUI interaction: click/double_click/right_click/move/drag/scroll/keys/text.

        Inspect screenshots before/after. Coordinates use the full desktop screenshot.
        OrcaSlicer must be foreground. Dialogs and permissions may need local handling.
        """
        return await asyncio.to_thread(desktop.action, action, x, y, text, keys, amount)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Standalone OrcaSlicer MCP (stdio)")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--doctor", action="store_true", help="Print CLI capabilities as JSON, then exit"
    )
    parser.add_argument("--output", type=Path, help="Save doctor report as JSON")
    args = parser.parse_args()
    if args.doctor:
        import json

        engine = Engine(
            Path(os.environ.get("ORCA_MCP_STATE", str(Path.home() / ".rrs-orca"))) / "doctor"
        )
        report = asyncio.run(engine.capabilities(True))
        if args.output:
            atomic_json(args.output, report)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["available"] else 1)
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
