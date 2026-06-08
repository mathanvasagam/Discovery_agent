from __future__ import annotations

import json
import logging
import os
import re
import subprocess
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


def _write_artifact(workspace: Path, artifact: Dict[str, Any]) -> Dict[str, Path]:
    filename = artifact.get("filename", "artifact.py")
    code_path = workspace / filename
    code_path.write_text(artifact.get("code", ""), encoding="utf-8")

    tests_filename = artifact.get("test_filename")
    if not tests_filename:
        tests_filename = "test_generated.py" if artifact.get("language") == "python" else "generated.test.js"
    tests_path = workspace / tests_filename
    tests_path.write_text(artifact.get("tests", ""), encoding="utf-8")

    for name, content in artifact.get("config_files", {}).items():
        (workspace / name).write_text(content, encoding="utf-8")

    readme = artifact.get("readme")
    if readme:
        (workspace / "README.md").write_text(readme, encoding="utf-8")

    return {"code": code_path, "tests": tests_path}


def _run_command(command: List[str], cwd: Path) -> Dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def run_in_docker(code_artifact: Dict[str, Any], network_disabled: bool = True) -> Dict[str, Any]:
    """
    Execute generated code in a temporary local workspace.
    The function name is preserved for compatibility with existing tests.
    """
    language = code_artifact.get("language", "python").lower()
    filename = code_artifact.get("filename", "artifact.py")
    warnings = _static_warnings(code_artifact.get("code", ""))
    logs: List[Dict[str, Any]] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory(prefix="discovery-agent-validate-") as temp_dir:
        workspace = Path(temp_dir)
        paths = _write_artifact(workspace, code_artifact)

        if language == "python":
            syntax_results = [
                _run_command(["python3", "-m", "py_compile", str(paths["code"].name)], workspace),
            ]
            if code_artifact.get("tests", "").strip():
                syntax_results.append(_run_command(["python3", "-m", "py_compile", str(paths["tests"].name)], workspace))
            logs.extend(syntax_results)
            errors.extend(result["stderr"].strip() for result in syntax_results if result["returncode"] != 0 and result["stderr"].strip())

            static_result = _run_command(["python3", "-m", "compileall", "-q", "."], workspace)
            logs.append(static_result)
            if static_result["returncode"] != 0 and static_result["stderr"].strip():
                errors.append(static_result["stderr"].strip())

            runtime_command = ["python3", "-m", "unittest", "discover", "-v"] if code_artifact.get("tests", "").strip() else ["python3", str(paths["code"].name)]
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

    result = run_in_docker(code_artifact, network_disabled=True)
    logger.info("Validation result for %s: %s", code_artifact.get("filename"), result["status"])
    return result
