from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


logger = logging.getLogger(__name__)

SUPPORTED_SANDBOX_LANGUAGES = ["python", "nodejs"]


def _static_warnings(code: str) -> List[str]:
    warnings: List[str] = []
    if "TODO" in code:
        warnings.append("Code contains TODO markers.")
    if re.search(r"except\s*:\s", code):
        warnings.append("Bare except detected.")
    if re.search(r"password\s*=\s*['\"]", code, flags=re.IGNORECASE):
        warnings.append("Potential hardcoded secret detected.")
    return warnings


def _safe_workspace_name(name: str, default: str) -> str:
    normalized = str(name or default).replace("\\", "/")
    basename = Path(normalized).name
    return basename if basename not in {"", ".", ".."} else default


def _write_artifact(workspace: Path, artifact: Dict[str, Any]) -> Dict[str, Path]:
    filename = _safe_workspace_name(str(artifact.get("filename", "artifact.py")), "artifact.py")
    code_path = workspace / filename
    code_path.write_text(artifact.get("code", ""), encoding="utf-8")

    tests_filename = artifact.get("test_filename")
    if not tests_filename:
        tests_filename = "test_generated.py" if artifact.get("language") == "python" else "generated.test.js"
    tests_filename = _safe_workspace_name(str(tests_filename), "test_generated.py")
    tests_path = workspace / tests_filename
    tests_path.write_text(artifact.get("tests", ""), encoding="utf-8")

    for name, content in artifact.get("config_files", {}).items():
        safe_name = _safe_workspace_name(str(name), "config.txt")
        (workspace / safe_name).write_text(content, encoding="utf-8")

    readme = artifact.get("readme")
    if readme:
        (workspace / "README.md").write_text(readme, encoding="utf-8")

    return {"code": code_path, "tests": tests_path}


def _ensure_workspace_accessible_for_container(workspace: Path) -> None:
    try:
        workspace.chmod(0o755)
        for item in workspace.iterdir():
            if item.is_file():
                item.chmod(0o644)
    except OSError as exc:
        logger.warning("Could not normalize workspace permissions for container execution: %s", exc)


def _run_command(command: List[str], cwd: Path, timeout_seconds: int = 20) -> Dict[str, Any]:
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": f"Validation command timed out after {timeout_seconds} seconds.",
        }
    except FileNotFoundError as exc:
        return {
            "command": command,
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
        }


def _docker_available(cwd: Path) -> bool:
    result = _run_command(["docker", "info", "--format", "{{.ServerVersion}}"], cwd, timeout_seconds=5)
    return result["returncode"] == 0


def _docker_exec(workspace: Path, image: str, inner_command: List[str]) -> Dict[str, Any]:
    user_flags: List[str] = []
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        user_flags = ["--user", f"{os.getuid()}:{os.getgid()}"]

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        os.getenv("DISCOVERY_SANDBOX_MEMORY", "256m"),
        "--cpus",
        os.getenv("DISCOVERY_SANDBOX_CPUS", "1.0"),
        "--pids-limit",
        os.getenv("DISCOVERY_SANDBOX_PIDS", "128"),
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "-v",
        f"{workspace.resolve()}:/workspace:rw",
        "-w",
        "/workspace",
        *user_flags,
        image,
        "timeout",
        "15s",
        *inner_command,
    ]
    return _run_command(command, workspace, timeout_seconds=20)


def _run_local_validation(code_artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Development-only host validation for trusted code."""
    network_disabled = False
    language = code_artifact.get("language", "python").lower()
    filename = code_artifact.get("filename", "artifact.py")
    warnings = _static_warnings(code_artifact.get("code", ""))
    logs: List[Dict[str, Any]] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory(prefix="discovery-agent-validate-") as temp_dir:
        workspace = Path(temp_dir)
        paths = _write_artifact(workspace, code_artifact)

        if language == "python":
            python_executable = sys.executable or "python"
            syntax_results = [
                _run_command([python_executable, "-m", "py_compile", str(paths["code"].name)], workspace),
            ]
            if code_artifact.get("tests", "").strip():
                syntax_results.append(_run_command([python_executable, "-m", "py_compile", str(paths["tests"].name)], workspace))
            logs.extend(syntax_results)
            errors.extend(result["stderr"].strip() for result in syntax_results if result["returncode"] != 0 and result["stderr"].strip())

            static_result = _run_command([python_executable, "-m", "compileall", "-q", "."], workspace)
            logs.append(static_result)
            if static_result["returncode"] != 0 and static_result["stderr"].strip():
                errors.append(static_result["stderr"].strip())

            runtime_command = [python_executable, "-m", "unittest", "discover", "-v"] if code_artifact.get("tests", "").strip() else [python_executable, str(paths["code"].name)]
            runtime_result = _run_command(runtime_command, workspace)
            logs.append(runtime_result)
            if runtime_result["returncode"] != 0:
                runtime_error = runtime_result["stderr"].strip() or runtime_result["stdout"].strip() or "Runtime validation failed."
                errors.append(runtime_error)

        elif language == "nodejs":
            syntax_results = [_run_command(["node", "--check", str(paths["code"].name)], workspace)]
            if code_artifact.get("tests", "").strip():
                syntax_results.append(_run_command(["node", "--check", str(paths["tests"].name)], workspace))
            logs.extend(syntax_results)
            errors.extend(result["stderr"].strip() for result in syntax_results if result["returncode"] != 0 and result["stderr"].strip())

            runtime_command = ["node", "--test"] if code_artifact.get("tests", "").strip() else ["node", str(paths["code"].name)]
            runtime_result = _run_command(runtime_command, workspace)
            logs.append(runtime_result)
            if runtime_result["returncode"] != 0:
                runtime_error = runtime_result["stderr"].strip() or runtime_result["stdout"].strip() or "Runtime validation failed."
                errors.append(runtime_error)
        else:
            return {
                "status": "fail",
                "output": f"Unsupported sandbox language: {language}",
                "warnings": warnings,
                "errors": [f"Unsupported sandbox language: {language}"],
                "logs": [],
                "network_disabled": network_disabled,
            }

    status = "pass" if not errors else "fail"
    summary = "Validation passed." if status == "pass" else "Validation failed."
    return {
        "status": status,
        "output": summary,
        "warnings": warnings,
        "errors": errors,
        "logs": logs,
        "network_disabled": network_disabled,
        "isolation": "local-development",
        "filename": filename,
    }


def _run_static_validation(code_artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Syntax-only validation for public hosted deployments; generated code is never executed."""
    language = code_artifact.get("language", "python").lower()
    filename = code_artifact.get("filename", "artifact.py")
    warnings = _static_warnings(code_artifact.get("code", ""))
    warnings.append("Hosted static validation does not execute generated code.")
    logs: List[Dict[str, Any]] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory(prefix="discovery-agent-static-") as temp_dir:
        workspace = Path(temp_dir)
        paths = _write_artifact(workspace, code_artifact)

        if language == "python":
            python_executable = sys.executable or "python"
            commands = [[python_executable, "-m", "py_compile", paths["code"].name]]
            if code_artifact.get("tests", "").strip():
                commands.append([python_executable, "-m", "py_compile", paths["tests"].name])
        elif language == "nodejs":
            commands = [["node", "--check", paths["code"].name]]
            if code_artifact.get("tests", "").strip():
                commands.append(["node", "--check", paths["tests"].name])
        else:
            commands = []
            errors.append(f"Unsupported sandbox language: {language}")

        for command in commands:
            result = _run_command(command, workspace, timeout_seconds=10)
            logs.append(result)
            if result["returncode"] != 0:
                errors.append(result["stderr"].strip() or result["stdout"].strip() or "Static validation failed.")

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "output": "Static validation passed; runtime execution was intentionally skipped." if status == "pass" else "Static validation failed.",
        "warnings": warnings,
        "errors": errors,
        "logs": logs,
        "network_disabled": True,
        "execution_performed": False,
        "isolation": "static-only",
        "filename": filename,
    }


def run_in_docker(code_artifact: Dict[str, Any], network_disabled: bool = True) -> Dict[str, Any]:
    """Execute generated code inside a constrained, network-disabled Docker container."""
    language = code_artifact.get("language", "python").lower()
    filename = code_artifact.get("filename", "artifact.py")
    warnings = _static_warnings(code_artifact.get("code", ""))
    logs: List[Dict[str, Any]] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory(prefix="discovery-agent-validate-") as temp_dir:
        workspace = Path(temp_dir)
        paths = _write_artifact(workspace, code_artifact)
        _ensure_workspace_accessible_for_container(workspace)

        if not _docker_available(workspace):
            return {
                "status": "fail",
                "output": "Secure validation requires a running Docker engine.",
                "warnings": warnings,
                "errors": [
                    "Docker is unavailable. Start Docker, or set DISCOVERY_VALIDATION_MODE=local only for trusted development code."
                ],
                "logs": [],
                "network_disabled": True,
                "isolation": "docker-unavailable",
                "filename": filename,
            }

        image = (
            os.getenv("DISCOVERY_PYTHON_SANDBOX_IMAGE", "discovery-agent-python-sandbox:3.12")
            if language == "python"
            else os.getenv("DISCOVERY_NODE_SANDBOX_IMAGE", "node:22-alpine")
        )

        if language == "python":
            commands = [["python", "-m", "py_compile", paths["code"].name]]
            if code_artifact.get("tests", "").strip():
                commands.append(["python", "-m", "py_compile", paths["tests"].name])
            commands.append(["python", "-m", "compileall", "-q", "."])
            if code_artifact.get("tests", "").strip():
                if "pytest" in code_artifact.get("tests", ""):
                    commands.append(["python", "-m", "pytest", "-q"])
                else:
                    commands.append(["python", "-m", "unittest", "discover", "-v"])
            else:
                commands.append(["python", paths["code"].name])
        else:
            commands = [["node", "--check", paths["code"].name]]
            if code_artifact.get("tests", "").strip():
                commands.append(["node", "--check", paths["tests"].name])
                commands.append(["node", "--test"])
            else:
                commands.append(["node", paths["code"].name])

        for command in commands:
            result = _docker_exec(workspace, image, command)
            logs.append(result)
            if result["returncode"] != 0:
                errors.append(result["stderr"].strip() or result["stdout"].strip() or "Container validation failed.")

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "output": "Validation passed." if status == "pass" else "Validation failed.",
        "warnings": warnings,
        "errors": errors,
        "logs": logs,
        "network_disabled": network_disabled,
        "isolation": "docker",
        "filename": filename,
    }


def validate_code_in_sandbox(code_artifact: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a generated artifact with syntax, static, and runtime checks.
    """
    if not code_artifact or "code" not in code_artifact:
        logger.error("Invalid code artifact provided: missing 'code'.")
        return {"status": "fail", "output": "Invalid code artifact provided.", "warnings": [], "errors": ["Missing code"], "logs": []}

    language = code_artifact.get("language", "python").lower()
    if language not in SUPPORTED_SANDBOX_LANGUAGES:
        msg = f"Unsupported sandbox language: {language}"
        return {"status": "fail", "output": msg, "warnings": [], "errors": [msg], "logs": []}

    validation_mode = os.getenv("DISCOVERY_VALIDATION_MODE", "docker").strip().lower()
    if validation_mode == "static":
        result = _run_static_validation(code_artifact)
    elif validation_mode == "local":
        result = _run_local_validation(code_artifact)
        result.setdefault("warnings", []).append(
            "Development-only local validation is enabled; generated code executes on the host."
        )
    elif validation_mode == "docker":
        result = run_in_docker(code_artifact, network_disabled=True)
    else:
        msg = f"Unsupported validation mode: {validation_mode}. Use 'static', 'docker', or 'local'."
        return {"status": "fail", "output": msg, "warnings": [], "errors": [msg], "logs": []}

    logger.info("Validation result for %s: %s", code_artifact.get("filename"), result["status"])
    return result
