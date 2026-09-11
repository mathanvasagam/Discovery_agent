from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
NODE_MODULES = FRONTEND_DIR / "node_modules"


@dataclass
class VerificationSummary:
    passed: list[str]
    skipped: list[str]


def _which(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def _display_command(command: Sequence[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def run_required(label: str, command: Sequence[str], *, cwd: Path) -> None:
    print(f"\n==> {label}")
    print(f"    {_display_command(command)}")
    result = subprocess.run(list(command), cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}.")
    print(f"[PASS] {label}")


def _frontend_commands(node: str) -> list[tuple[str, list[str]]]:
    if not NODE_MODULES.exists():
        raise RuntimeError("frontend/node_modules is missing. Run 'cd frontend && npm ci' before verification.")

    eslint = NODE_MODULES / "eslint" / "bin" / "eslint.js"
    vitest = NODE_MODULES / "vitest" / "vitest.mjs"
    tsc = NODE_MODULES / "typescript" / "bin" / "tsc"
    vite = NODE_MODULES / "vite" / "bin" / "vite.js"
    required_files = (eslint, vitest, tsc, vite)
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise RuntimeError(f"Frontend dependency entry points are missing: {', '.join(missing)}. Run npm ci.")

    return [
        ("Frontend lint", [node, str(eslint), "."]),
        ("Frontend tests", [node, str(vitest), "run"]),
        ("Frontend TypeScript build", [node, str(tsc), "-b"]),
        ("Frontend Vite production build", [node, str(vite), "build"]),
    ]


def _compose_command() -> list[str] | None:
    docker = _which("docker")
    if docker:
        probe = subprocess.run([docker, "compose", "version"], cwd=ROOT, capture_output=True, text=True, check=False)
        if probe.returncode == 0:
            return [docker, "compose", "config", "--quiet"]

    compose = _which("docker-compose", "docker-compose.exe")
    if compose:
        return [compose, "config", "--quiet"]
    return None


def verify(*, include_compose: bool = True) -> VerificationSummary:
    summary = VerificationSummary(passed=[], skipped=[])

    backend_steps = [
        ("Backend tests", [sys.executable, "-m", "pytest", "core", "-q"], BACKEND_DIR),
        ("Backend compile check", [sys.executable, "-m", "compileall", "-q", "."], BACKEND_DIR),
    ]
    for label, command, cwd in backend_steps:
        run_required(label, command, cwd=cwd)
        summary.passed.append(label)

    node = _which("node")
    if not node:
        raise RuntimeError("Node.js was not found in PATH. Install Node.js 22+ before verification.")
    for label, command in _frontend_commands(node):
        run_required(label, command, cwd=FRONTEND_DIR)
        summary.passed.append(label)

    if include_compose:
        compose_command = _compose_command()
        if compose_command:
            run_required("Docker Compose configuration", compose_command, cwd=ROOT)
            summary.passed.append("Docker Compose configuration")
        else:
            message = "Docker Compose configuration (Docker/Compose CLI unavailable)"
            print(f"\n[SKIP] {message}")
            summary.skipped.append(message)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Discovery Agent repository quality gates.")
    parser.add_argument("--no-compose", action="store_true", help="Skip Docker Compose configuration validation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Discovery Agent verification")
    print(f"Repository: {ROOT}")
    try:
        summary = verify(include_compose=not args.no_compose)
    except (OSError, RuntimeError) as exc:
        print(f"\n[FAIL] {exc}")
        return 1

    print("\nVerification summary")
    for label in summary.passed:
        print(f"  PASS  {label}")
    for label in summary.skipped:
        print(f"  SKIP  {label}")
    print("\nAll required quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
