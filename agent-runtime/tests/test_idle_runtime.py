from __future__ import annotations

import ast
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tomllib
import unittest


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
MAIN_MODULE = RUNTIME_ROOT / "src" / "agent_runtime" / "__main__.py"


def _read_line(stream: object, output: queue.Queue[str]) -> None:
    output.put(stream.readline())


def _cleanup_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.wait(timeout=5)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()


def _windows_listening_ports(process_id: int) -> set[str]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        fields[1]
        for line in result.stdout.splitlines()
        if (fields := line.split())
        and len(fields) >= 5
        and fields[-2].upper() == "LISTENING"
        and fields[-1] == str(process_id)
    }


def _linux_listening_ports(process_id: int) -> set[str]:
    fd_root = Path("/proc") / str(process_id) / "fd"
    socket_inodes = {
        target.removeprefix("socket:[").removesuffix("]")
        for descriptor in fd_root.iterdir()
        if (target := os.readlink(descriptor)).startswith("socket:[")
    }
    listeners: set[str] = set()
    for table_name in ("tcp", "tcp6"):
        table = Path("/proc/net") / table_name
        if not table.exists():
            continue
        for line in table.read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) > 9 and fields[3] == "0A" and fields[9] in socket_inodes:
                listeners.add(fields[1])
    return listeners


def _listening_ports(process_id: int) -> set[str]:
    if os.name == "nt":
        return _windows_listening_ports(process_id)
    if Path("/proc").exists():
        return _linux_listening_ports(process_id)
    raise unittest.SkipTest("listener ownership inspection is unavailable")


class IdleRuntimeTest(unittest.TestCase):

    def test_metadata_has_only_locked_contract_dependencies_and_no_local_environment(self) -> None:
        metadata = tomllib.loads((RUNTIME_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            ["pydantic==2.13.4", "jsonschema==4.26.0"],
            metadata["project"]["dependencies"],
        )
        self.assertEqual(">=3.12,<3.13", metadata["project"]["requires-python"])
        self.assertFalse((RUNTIME_ROOT / ".env").exists())

    def test_entrypoint_imports_only_idle_standard_library_modules(self) -> None:
        syntax = ast.parse(MAIN_MODULE.read_text(encoding="utf-8"))
        imports = {
            imported
            for node in ast.walk(syntax)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for imported in (
                [node.module] if isinstance(node, ast.ImportFrom) else [alias.name for alias in node.names]
            )
        }
        self.assertEqual({"__future__", "signal", "threading"}, imports)

    def test_process_starts_terminates_and_does_not_listen(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(RUNTIME_ROOT / "src")
        process = subprocess.Popen(
            [sys.executable, "-m", "agent_runtime"],
            cwd=RUNTIME_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(_cleanup_process, process)

        ready_lines: queue.Queue[str] = queue.Queue()
        reader = threading.Thread(
            target=_read_line,
            args=(process.stdout, ready_lines),
            daemon=True,
        )
        reader.start()
        self.assertEqual("agent-runtime idle", ready_lines.get(timeout=5).strip())
        self.assertIsNone(process.poll())
        self.assertEqual(set(), _listening_ports(process.pid))

        process.terminate()
        process.wait(timeout=5)
        self.assertIsNotNone(process.returncode)


if __name__ == "__main__":
    unittest.main()
