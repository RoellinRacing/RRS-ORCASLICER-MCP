"""Exercise resumable single slicing over actual MCP stdio and the stock CLI.

Run after smoke_orca.py; inputs are its saved cube and resolved profiles. Reports
are checkpointed before submitting work and after every completed observation.
"""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rrs_orcaslicer_mcp.storage import atomic_json, digest


async def main():
    root = Path(os.environ.get("ORCA_TEST_OUTPUT", "smoke-output")).resolve()
    report_path = root / "resumable-jobs.json"
    request = {
        "inputs": [str(root / "cube.stl")],
        "settings": [str(root / "machine.json"), str(root / "process.json")],
        "filaments": [str(root / "filament.json")],
        "output_directory": str(root / "resumable-output"),
        "export_3mf": "resumable.3mf",
        "idempotency_key": "stock-cli-resumable-0.5.1",
        "timeout_seconds": 300,
    }
    ident = hashlib.sha256(("slice_project:" + request["idempotency_key"]).encode()).hexdigest()[
        :32
    ]
    report = {"phase": "prepared", "request": request, "job_id": ident, "physical_print": False}
    atomic_json(report_path, report)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "rrs_orcaslicer_mcp.server"],
        env={**os.environ, "ORCA_MCP_ROOTS": str(root), "ORCA_MCP_STATE": str(root / "mcp-state")},
    )

    async def checked(client, name, args):
        value = await client.call_tool(name, args)
        if value.isError:
            raise AssertionError(f"{name}: {value.content}")
        return value.structuredContent

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            report["tool_count"] = len((await client.list_tools()).tools)
            assert report["tool_count"] == 63
            first, duplicate = await asyncio.gather(
                *[checked(client, "slice_project", request) for _ in range(2)]
            )
            assert first["id"] == duplicate["id"] == ident
            report.update(phase="submitted", expected_files=first["expected_files"])
            atomic_json(report_path, report)
            for _ in range(40):
                job = await checked(client, "job_wait", {"job_id": ident, "timeout_seconds": 10})
                report.update(phase="observing", job=job)
                atomic_json(report_path, report)
                if job["status"] not in {"queued", "running"}:
                    break
            assert job["status"] == "succeeded", job
            chunks, offset = [], 0
            while True:
                part = await checked(client, "job_log", {"job_id": ident, "offset": offset})
                chunks.append(part["text"])
                offset = part["next_offset"]
                if part["at_end"]:
                    break
            assert offset > 0
            report.update(phase="sliced", log_bytes=offset, log_text="".join(chunks))
            atomic_json(report_path, report)
    # A separate server process must return the same completed job, not reslice.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            again = await checked(client, "slice_project", request)
            assert again["id"] == ident and again["status"] == "succeeded"
            assert again["started"] == job["started"] and again["finished"] == job["finished"]
            saved = await checked(client, "job_log", {"job_id": ident, "offset": offset})
            assert saved["at_end"] and saved["text"] == ""
            conflict = await client.call_tool("slice_project", {**request, "plate": 1})
            assert conflict.isError
    outputs = sorted((root / "resumable-output").rglob("*"))
    outputs = [p for p in outputs if p.is_file() and p.suffix in {".3mf", ".gcode"}]
    assert any(p.suffix == ".gcode" and p.stat().st_size > 0 for p in outputs)
    assert (root / "resumable-output/resumable.3mf").is_file()
    assert len(list((root / "mcp-state/jobs").glob("*/job.json"))) == 1
    report.update(
        phase="finished",
        status="succeeded",
        restart_verified=True,
        artifacts=[
            {"path": str(p), "size": p.stat().st_size, "sha256": digest(p)} for p in outputs
        ],
    )
    atomic_json(report_path, report)
    print(
        json.dumps(
            {"status": report["status"], "tool_count": report["tool_count"], "job_id": ident}
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
