from pathlib import Path
import importlib

from fastapi.testclient import TestClient


def load(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODESTRA_AUTH_MODE", "development")
    monkeypatch.setenv("CODESTRA_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("CODESTRA_INPUT_ROOT", str(tmp_path / "inputs"))
    monkeypatch.setenv("CODESTRA_OUTPUT_ROOT", str(tmp_path / "outputs"))
    import codestra_saas
    return importlib.reload(codestra_saas)


def test_health_ready_and_idempotency(tmp_path, monkeypatch):
    mod = load(tmp_path, monkeypatch); client = TestClient(mod.app)
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    h={"X-Tenant-ID":"t1","X-Actor-ID":"a1","Idempotency-Key":"idem-0001"}
    p={"kind":"render_timeline","project_id":"p1","parameters":{}}
    one=client.post("/v1/jobs",headers=h,json=p); two=client.post("/v1/jobs",headers=h,json=p)
    assert one.status_code == 202 and one.json()["id"] == two.json()["id"]
    found=client.get("/v1/jobs/by-idempotency",headers={"X-Tenant-ID":"t1"},params={"idempotency_key":"idem-0001"})
    assert found.status_code == 200 and found.json()["id"] == one.json()["id"]
    assert client.get(f"/v1/jobs/{one.json()['id']}",headers={"X-Tenant-ID":"other"}).status_code == 404


def test_mlt_command_is_bounded(tmp_path, monkeypatch):
    mod = load(tmp_path, monkeypatch)
    src=mod.settings.input_root / "project.kdenlive"; src.parent.mkdir(parents=True,exist_ok=True); src.write_text("<mlt/>")
    job={"kind":"render_timeline","parameters":{"source_path":"project.kdenlive","output_path":"final.mp4","vcodec":"libx264","acodec":"aac","crf":20}}
    cmd=mod.command_for(job)
    assert cmd[:2] == ["melt",str(src.resolve())]
    assert cmd[2:4] == ["-consumer",f"avformat:{(mod.settings.output_root / 'final.mp4').resolve()}"]
    assert "vcodec=libx264" in cmd and "acodec=aac" in cmd and "crf=20" in cmd
    bad={"kind":"render_timeline","parameters":{"source_path":"../escape.kdenlive"}}
    try: mod.command_for(bad)
    except ValueError as exc: assert str(exc) == "path_outside_workspace"
    else: raise AssertionError("path traversal accepted")
