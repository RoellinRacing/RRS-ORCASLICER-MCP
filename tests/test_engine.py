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
    script = tmp_path / "worker-温度.py"
    script.write_text("import sys; print(sys.argv[1]); sys.exit(3 if '--fail' in sys.argv else 0)")
    marker = tmp_path / "must-not-exist"
    job = await engine.submit([str(script), f"$(touch {marker})"])
    done = await wait(engine, job["id"])
    assert done["status"] == "succeeded"
    assert not marker.exists()
    assert "$(touch" in (tmp_path / "jobs" / job["id"] / "output.log").read_text(encoding="utf-8")
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


async def test_concurrent_submission_has_one_receipt_and_one_execution(engine, tmp_path):
    script = tmp_path / "counter.py"
    counter = tmp_path / "counter.txt"
    script.write_text(
        "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.open('a').write('run\\n')"
    )
    probes = 0

    async def slow_caps(refresh=False):
        nonlocal probes
        probes += 1
        await asyncio.sleep(0.02)
        return {"available": True, "flags": []}

    engine.capabilities = slow_caps
    try:
        jobs = await asyncio.gather(
            *[engine.submit([str(script), str(counter)], job_id="b" * 32) for _ in range(8)]
        )
        assert len({j["id"] for j in jobs}) == 1
        assert (await engine.wait(jobs[0]["id"], 5))["status"] == "succeeded"
        assert counter.read_text() == "run\n"
        assert probes == 1
        with pytest.raises(ValueError, match="different inputs"):
            await engine.submit([str(script)], job_id="b" * 32)
    finally:
        await engine.close()


async def test_wait_timeout_and_cancelled_observer_leave_job_running(engine, tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(60)")
    try:
        job = await engine.submit([str(script)])
        ident = job["id"]
        assert (await engine.wait(ident, 0.01))["status"] == "running"
        watcher = asyncio.create_task(engine.wait(ident, 30))
        await asyncio.sleep(0)
        watcher.cancel()
        with pytest.raises(asyncio.CancelledError):
            await watcher
        assert not engine.tasks[ident].done()
        for invalid in (-1, 31, float("nan"), float("inf")):
            with pytest.raises(ValueError, match="Wait timeout"):
                await engine.wait(ident, invalid)
        assert (await engine.cancel(ident))["status"] == "cancelled"
        assert (await engine.wait(ident, 0))["status"] == "cancelled"
    finally:
        await engine.close()


async def test_log_cursors_preserve_unicode_and_survive_restart(engine, tmp_path):
    script = tmp_path / "unicode.py"
    script.write_text(
        "import sys; sys.stdout.buffer.write('A温度🙂B'.encode('utf-8'))", encoding="utf-8"
    )
    job = await engine.submit([str(script)])
    ident = job["id"]
    await engine.wait(ident, 5)
    chunks, offset = [], 0
    while True:
        part = engine.read_log(ident, offset, 4)
        chunks.append(part["text"])
        assert part["next_offset"] > offset
        offset = part["next_offset"]
        if part["at_end"]:
            break
    assert "".join(chunks) == "A温度🙂B"
    assert engine.read_log(ident, offset)["text"] == ""
    for cursor, limit in ((-1, 4), (offset + 1, 4), (0, 0), (0, 100001)):
        with pytest.raises(ValueError):
            engine.read_log(ident, cursor, limit)
    await engine.close()
    restarted = Engine(engine.state, binary=sys.executable)
    try:
        assert restarted.read_log(ident, 1, 6)["text"] == "温度"
        assert (await restarted.wait(ident))["status"] == "succeeded"
        assert not restarted.tasks
    finally:
        await restarted.close()


async def test_saved_log_never_exceeds_cap(engine, tmp_path):
    script = tmp_path / "verbose.py"
    script.write_text("import sys; sys.stdout.buffer.write(b'x' * (10*1024*1024+12345))")
    try:
        job = await engine.submit([str(script)])
        done = await engine.wait(job["id"], 5)
        assert done["status"] == "succeeded"
        assert done["log_truncated"] is True
        from pathlib import Path

        assert Path(done["log"]).stat().st_size == 10 * 1024 * 1024
    finally:
        await engine.close()


async def test_log_cursor_waits_for_incomplete_live_utf8(engine, tmp_path):
    from pathlib import Path

    script = tmp_path / "idle.py"
    script.write_text("pass")
    job = await engine.submit([str(script)])
    await engine.wait(job["id"], 5)
    path = Path(job["log"])
    saved = Path(job["directory"]) / "job.json"
    job["status"] = "running"
    saved.write_text(json.dumps(job))
    encoded = "温".encode()
    path.write_bytes(encoded[:2])
    part = engine.read_log(job["id"])
    assert part["text"] == "" and part["next_offset"] == 0
    path.write_bytes(encoded)
    assert engine.read_log(job["id"])["text"] == "温"
    await engine.close()


async def test_retry_reclaims_folder_left_before_receipt_write(engine, tmp_path):
    ident = "c" * 32
    (engine.state / ident).mkdir()  # simulated crash after mkdir, before job.json
    script = tmp_path / "ok.py"
    script.write_text("print('ok')")
    try:
        job = await engine.submit([str(script)], job_id=ident)
        assert (await engine.wait(job["id"], 5))["status"] == "succeeded"
        assert (await engine.submit([str(script)], job_id=ident))["status"] == "succeeded"
    finally:
        await engine.close()
