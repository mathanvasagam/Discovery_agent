import os
from pathlib import Path

from core.sandbox import _docker_exec, _ensure_workspace_accessible_for_container


def test_ensure_workspace_accessible_for_container_sets_readable_permissions(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "stripe_connector.py"
    tests = workspace / "test_generated.py"
    source.write_text("print('ok')", encoding="utf-8")
    tests.write_text("print('test')", encoding="utf-8")

    workspace.chmod(0o700)
    source.chmod(0o600)
    tests.chmod(0o600)

    _ensure_workspace_accessible_for_container(workspace)

    assert workspace.stat().st_mode & 0o777 == 0o755
    assert source.stat().st_mode & 0o777 == 0o644
    assert tests.stat().st_mode & 0o777 == 0o644


def test_docker_exec_runs_with_host_user_permissions(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured = {}

    def fake_run(command, cwd, timeout_seconds=20):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout_seconds"] = timeout_seconds
        return {"returncode": 0, "stdout": "ok", "stderr": "", "command": command}

    monkeypatch.setattr("core.sandbox._run_command", fake_run)

    _docker_exec(workspace, "discovery-agent-python-sandbox:3.12", ["python", "-V"])

    assert captured["cwd"] == workspace
    assert captured["timeout_seconds"] == 20
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        user_index = captured["command"].index("--user")
        assert captured["command"][user_index + 1] == f"{os.getuid()}:{os.getgid()}"
