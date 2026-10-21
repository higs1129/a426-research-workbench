#!/usr/bin/env python3
"""Run a declared source rebuild in a copy with retired inputs unavailable."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable, Mapping, Sequence


def _relative_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be relative to the isolated project root")
    return path


def _inside(path: Path, root: Path, label: str) -> Path:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must be inside {root}") from exc
    return path


def _overlap(first: Path, second: Path) -> bool:
    first, second = first.resolve(), second.resolve()
    return first == second or first in second.parents or second in first.parents


def run_isolated_rebuild(
    project_root: Path,
    command: Sequence[str],
    output: str | Path,
    unavailable: Sequence[str | Path] = (),
    cwd: str | Path = ".",
    *,
    isolation_root: Path,
    allowed_root: Path | None = None,
    output_validator: Callable[[Path], bool | Mapping[str, object]] | None = None,
    verify_command: Sequence[str] | None = None,
) -> dict:
    """Copy a project, omit retired inputs, run its command, and inspect output.

    The command must use explicit relative inputs/outputs. The source project is
    never modified and the temporary copy is removed after the check. The
    expected output is excluded from the copy, so an existing output cannot
    satisfy a no-op command. `output_validator` or `verify_command` is required
    to claim `verified`; without one the report is deliberately unverified.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"project root is not a directory: {root}")
    output_path = _relative_path(str(output), "output")
    cwd_path = _relative_path(str(cwd), "cwd")
    unavailable_paths = [_relative_path(str(item), "unavailable path") for item in unavailable]
    if output_validator is not None and verify_command is not None:
        raise ValueError("provide output_validator or verify_command, not both")
    isolation = Path(isolation_root).resolve()
    if not isolation.is_dir():
        raise ValueError(f"isolation root is not a directory: {isolation}")
    allowed = Path(allowed_root).resolve() if allowed_root is not None else Path(__file__).resolve().parents[1] / "tests"
    _inside(isolation, allowed, "isolation root")
    if _overlap(root, isolation):
        raise ValueError("project root and isolation root must not overlap")
    with tempfile.TemporaryDirectory(prefix="photonic-rebuild-", dir=isolation) as temporary:
        isolated = Path(temporary) / "project"
        excluded = {item.as_posix().rstrip("/") for item in unavailable_paths}
        excluded.add(output_path.as_posix().rstrip("/"))

        def ignore(current: str, names: list[str]) -> set[str]:
            current_path = Path(current)
            ignored = set()
            for name in names:
                relative = (current_path / name).relative_to(root).as_posix()
                if relative in excluded or any(relative.startswith(item + "/") for item in excluded):
                    ignored.add(name)
            return ignored

        shutil.copytree(root, isolated, ignore=ignore)
        run_cwd = isolated / cwd_path
        if not run_cwd.is_dir():
            raise ValueError(f"isolated cwd does not exist: {cwd_path}")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            list(command), cwd=run_cwd, env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        produced = isolated / output_path
        validation = {"ok": False, "mode": "missing", "reason": "no output validator declared"}
        if completed.returncode == 0 and produced.is_file():
            if output_validator is not None:
                try:
                    result = output_validator(produced)
                    validation = dict(result) if isinstance(result, Mapping) else {"ok": bool(result)}
                except Exception as exc:  # validator failure is an acceptance failure
                    validation = {"ok": False, "mode": "callback", "error": str(exc)}
                validation.setdefault("mode", "callback")
            elif verify_command is not None:
                command_to_run = [item.replace("{output}", output_path.as_posix()) for item in verify_command]
                checked = subprocess.run(
                    command_to_run, cwd=run_cwd, env=environment,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
                validation = {
                    "ok": checked.returncode == 0,
                    "mode": "command",
                    "command": command_to_run,
                    "returncode": checked.returncode,
                    "stdout": checked.stdout,
                    "stderr": checked.stderr,
                }
        return {
            "ok": completed.returncode == 0 and produced.is_file() and bool(validation.get("ok")),
            "generated": completed.returncode == 0 and produced.is_file(),
            "verified": bool(validation.get("ok")),
            "returncode": completed.returncode,
            "output": output_path.as_posix(),
            "output_exists": produced.is_file(),
            "unavailable": [item.as_posix() for item in unavailable_paths],
            "command": list(command),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "validation": validation,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, help="Expected output path relative to the isolated project")
    parser.add_argument("--cwd", default=".", help="Command working directory relative to the isolated project")
    parser.add_argument("--unavailable", action="append", default=[], help="Retired input path to omit; repeat as needed")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--isolation-root", required=True, type=Path, help="Existing writable root for the temporary copy")
    parser.add_argument("--allowed-root", type=Path, help="Root that must contain --isolation-root; defaults to this Skill's tests directory")
    parser.add_argument("--verify-command", help="Optional validator command as a JSON argv list; use {output} for the generated relative output")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command after --, for example -- python build.py --output result.json")
    args = parser.parse_args()
    if not args.command or args.command[0] != "--":
        parser.error("provide a rebuild command after --")
    verify_command = None
    if args.verify_command:
        try:
            verify_command = json.loads(args.verify_command)
        except json.JSONDecodeError as exc:
            parser.error(f"--verify-command must be a JSON argv list: {exc}")
        if not isinstance(verify_command, list) or not all(isinstance(item, str) for item in verify_command):
            parser.error("--verify-command must decode to a JSON list of strings")
    try:
        report = run_isolated_rebuild(
            args.project_root, args.command[1:], args.output, args.unavailable, args.cwd,
            isolation_root=args.isolation_root, allowed_root=args.allowed_root,
            verify_command=verify_command,
        )
    except (OSError, ValueError) as exc:
        report = {"ok": False, "error": str(exc)}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
