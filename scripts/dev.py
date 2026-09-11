from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
BACKEND_DIR = ROOT / "backend"
FRONTEND_NODE_MODULES = FRONTEND_DIR / "node_modules"
VITE_ENTRY = FRONTEND_NODE_MODULES / "vite" / "bin" / "vite.js"
DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 5173


@dataclass(frozen=True)
class RuntimeTools:
    python: str
    node: str
    npm: str | None


def _which(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def _command_output(command: Sequence[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    output = (result.stdout or result.stderr).strip()
    return result.returncode, output


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _backend_dependencies_available() -> tuple[bool, str]:
    code, output = _command_output(
        [
            sys.executable,
            "-c",
            "import fastapi, sqlmodel, uvicorn; print('FastAPI/SQLModel/Uvicorn imports OK')",
        ]
    )
    return code == 0, output


def preflight(*, backend_port: int, frontend_port: int, check_ports: bool = True) -> tuple[bool, RuntimeTools | None]:
    print("Discovery Agent development preflight")
    print(f"Repository: {ROOT}")
    print()

    python_executable = sys.executable
    print(f"[OK] Python: {python_executable} ({sys.version.split()[0]})")

    node = _which("node")
    if not node:
        print("[FAIL] Node.js was not found in PATH. Install Node.js 22+ and run frontend dependency installation.")
        return False, None
    node_code, node_version = _command_output([node, "--version"])
    if node_code != 0:
        print(f"[FAIL] Node.js could not be executed: {node_version}")
        return False, None
    print(f"[OK] Node.js: {node_version} ({node})")

    npm = _which("npm.cmd", "npm") if os.name == "nt" else _which("npm", "npm.cmd")
    if npm:
        npm_code, npm_version = _command_output([npm, "--version"])
        if npm_code == 0:
            print(f"[OK] npm: {npm_version} ({npm})")
        else:
            print(f"[WARN] npm is present but did not execute cleanly: {npm_version}")
    else:
        print("[WARN] npm was not found in PATH. Existing node_modules can still be used, but fresh dependency installation requires npm.")

    backend_ok, backend_message = _backend_dependencies_available()
    if not backend_ok:
        print("[FAIL] Backend Python dependencies are missing.")
        print("       Run: python -m pip install -r requirements.txt")
        if backend_message:
            print(f"       {backend_message}")
        return False, None
    print(f"[OK] Backend dependencies: {backend_message}")

    if not FRONTEND_NODE_MODULES.exists() or not VITE_ENTRY.exists():
        print("[FAIL] Frontend dependencies are not installed.")
        print("       Run: cd frontend && npm ci")
        return False, None
    print(f"[OK] Frontend dependencies: {FRONTEND_NODE_MODULES}")

    if check_ports:
        for label, port in (("Backend", backend_port), ("Frontend", frontend_port)):
            if not _port_available(port):
                print(f"[FAIL] {label} port {port} is already in use.")
                return False, None
            print(f"[OK] {label} port {port} is available")

    return True, RuntimeTools(python=python_executable, node=node, npm=npm)


def _ensure_runtime_directories() -> None:
    for relative in ("data", "data/uploads", "data/generated", "data/reports"):
        (BACKEND_DIR / relative).mkdir(parents=True, exist_ok=True)


def _popen(command: Sequence[str], *, cwd: Path) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "text": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(list(command), **kwargs)  # type: ignore[arg-type]


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        taskkill = _which("taskkill")
        if taskkill:
            subprocess.run(
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        else:
            process.terminate()
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()

    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


def run_development_stack(tools: RuntimeTools, *, backend_port: int, frontend_port: int) -> int:
    _ensure_runtime_directories()

    backend_command = [
        tools.python,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
    ]
    frontend_command = [
        tools.node,
        str(VITE_ENTRY),
        "--host",
        "127.0.0.1",
        "--port",
        str(frontend_port),
        "--strictPort",
    ]

    print()
    print("Starting Discovery Agent development stack")
    print(f"Backend : http://127.0.0.1:{backend_port}")
    print(f"Frontend: http://127.0.0.1:{frontend_port}")
    print("Press Ctrl+C to stop both processes.")
    print()

    backend = _popen(backend_command, cwd=ROOT)
    frontend = _popen(frontend_command, cwd=FRONTEND_DIR)
    processes = [("backend", backend), ("frontend", frontend)]

    try:
        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"\n{name.capitalize()} process exited with code {return_code}.")
                    return return_code if return_code != 0 else 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping development stack...")
        return 0
    finally:
        for _, process in processes:
            _stop_process(process)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Discovery Agent backend and frontend development servers.")
    parser.add_argument("--check", action="store_true", help="Run prerequisite and port checks without starting servers.")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, tools = preflight(backend_port=args.backend_port, frontend_port=args.frontend_port)
    if not ok or tools is None:
        return 1
    if args.check:
        print("\nPreflight passed. The development stack can be started with: python scripts/dev.py")
        return 0
    return run_development_stack(tools, backend_port=args.backend_port, frontend_port=args.frontend_port)


if __name__ == "__main__":
    raise SystemExit(main())
