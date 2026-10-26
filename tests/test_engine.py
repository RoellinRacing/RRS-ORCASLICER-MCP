import asyncio
import json
import sys

import pytest

from rrs_orcaslicer_mcp.engine import Engine, capture


@pytest.fixture
def engine(tmp_path):
    result = Engine(tmp_path / "jobs", binary=sys.executable)

    async def caps(refresh=False):
        return {"available": True, "flags": ["sleep", "fail"]}

    result.capabilities = caps
    return result


async def wait(engine, ident):
    await engine.tasks[ident]
    return engine.get(ident)


async def test_jobs_success_failure_no_shell_and_logs(engine, tmp_path):
    script = tmp_path / "worker.py"
    script.write_text("import sys; print(sys.argv[1]); sys.exit(3 if '--fail' in sys.argv else 0)")
    marker = tmp_path / "must-not-exist"
    job = await engine.submit([str(script), f"$(touch {marker})"])
    done = await wait(engine, job["id"])
    assert done["status"] == "succeeded"
    assert not marker.exists()
    assert "$(touch" in (tmp_path / "jobs" / job["id"] / "output.log").read_text()
    failed = await engine.submit([str(script), "--fail"])
    assert (await wait(engine, failed["id"]))["returncode"] == 3
    with pytest.raises(ValueError, match="does not advertise"):
        await engine.submit(["--invented"])
    await engine.close()


async def test_timeout_and_cancel(engine, tmp_path):
    script = tmp_path / "sleep.py"
    script.write_text("import time; print('started', flush=True); time.sleep(60)")
    job = await engine.submit([str(script)], timeout=1)
    assert (await wait(engine, job["id"]))["status"] == "timed_out"
    active = await engine.submit([str(script)])
    for _ in range(100):
        if active["id"] in engine.processes:
            break
        await asyncio.sleep(0.01)
    queued = await engine.submit([str(script)])
    assert (await engine.cancel(queued["id"]))["status"] == "cancelled"
    assert (await engine.cancel(active["id"]))["status"] == "cancelled"
    assert not engine.processes
    await engine.close()


async def test_restart_marks_incomplete_work(tmp_path):
    folder = tmp_path / "jobs" / ("a" * 32)
    folder.mkdir(parents=True)
    (folder / "job.json").write_text(json.dumps({"id": "a" * 32, "status": "running"}))
    engine = Engine(folder.parent, binary=sys.executable)
    assert engine.get("a" * 32)["status"] == "interrupted"
    await engine.close()


async def test_capture_timeout_reaps_process(tmp_path):
    with pytest.raises(TimeoutError):
        await capture([sys.executable, "-c", "import time; time.sleep(60)"], timeout=1)
