from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


LIFECYCLE_TYPES = {"task_started", "task_complete", "task_aborted", "turn_aborted"}
TERMINAL_TYPES = {"task_complete", "task_aborted", "turn_aborted"}
STATUS_BY_EVENT = {
    "task_started": "running",
    "task_complete": "completed",
    "task_aborted": "stopped",
    "turn_aborted": "stopped",
}


class CodexTaskCollector:
    """Read a minimal, privacy-bounded task summary from the local Codex state."""

    def __init__(
        self,
        codex_home: Path | None = None,
        *,
        tail_bytes: int = 4 * 1024 * 1024,
        recent_terminal_seconds: int = 90 * 60,
        stale_running_seconds: int = 6 * 60 * 60,
        now: Callable[[], float] = time.time,
    ) -> None:
        configured_home = os.environ.get("CODEX_HOME")
        self.codex_home = Path(
            codex_home
            or configured_home
            or (Path.home() / ".codex")
        )
        self.state_db = self.codex_home / "state_5.sqlite"
        self.session_index = self.codex_home / "session_index.jsonl"
        self.tail_bytes = tail_bytes
        self.recent_terminal_seconds = recent_terminal_seconds
        self.stale_running_seconds = stale_running_seconds
        self.now = now

    def collect(self) -> dict[str, object]:
        if not self.state_db.is_file():
            raise FileNotFoundError("Codex state database is unavailable")

        named_threads = self._load_thread_names()
        rows = self._load_candidate_threads()
        now_ms = int(self.now() * 1000)
        tasks: list[dict[str, object]] = []

        for row in rows:
            thread_id = str(row["id"])
            source = str(row["source"] or "")
            thread_source = str(row["thread_source"] or "")
            agent_path = str(row["agent_path"] or "")
            if thread_source == "subagent" or agent_path or source.startswith("{"):
                continue
            if source != "vscode" and thread_id not in named_threads:
                continue

            rollout_path = Path(str(row["rollout_path"]))
            lifecycle = self._last_lifecycle_event(rollout_path)
            if lifecycle is None:
                continue

            event_type, event_ms = lifecycle
            status = STATUS_BY_EVENT[event_type]
            try:
                file_updated_ms = int(rollout_path.stat().st_mtime * 1000)
            except OSError:
                file_updated_ms = event_ms

            if status == "running":
                if now_ms - file_updated_ms > self.stale_running_seconds * 1000:
                    status = "stopped"
                    updated_ms = file_updated_ms
                else:
                    updated_ms = max(event_ms, file_updated_ms)
            else:
                updated_ms = event_ms

            if status != "running" and now_ms - updated_ms > self.recent_terminal_seconds * 1000:
                continue

            name = named_threads.get(thread_id) or str(row["name"] or "")
            if not name:
                name = self._short_title(str(row["title"] or "未命名任务"))

            tasks.append(
                {
                    "name": self._clean_name(name),
                    "status": status,
                    "updated_at_ms": updated_ms,
                }
            )

        order = {"running": 0, "completed": 1, "stopped": 2}
        tasks.sort(key=lambda task: (order[str(task["status"])], -int(task["updated_at_ms"])))
        active_count = sum(task["status"] == "running" for task in tasks)
        return {
            "ok": True,
            "host": os.environ.get("CODEX_WIDGET_HOST", "A426"),
            "generated_at_ms": now_ms,
            "active_count": active_count,
            "tasks": tasks[:8],
        }

    def _load_thread_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        if not self.session_index.is_file():
            return names
        with self.session_index.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except (ValueError, TypeError):
                    continue
                thread_id = str(item.get("id") or "").strip()
                thread_name = self._clean_name(str(item.get("thread_name") or ""))
                if thread_id and thread_name:
                    names[thread_id] = thread_name
        return names

    def _load_candidate_threads(self) -> list[sqlite3.Row]:
        uri = f"file:{self.state_db.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=1)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                """
                SELECT id, rollout_path, title, name, source, thread_source, agent_path,
                       COALESCE(updated_at_ms, updated_at * 1000, 0) AS sort_time
                FROM threads
                WHERE archived = 0
                ORDER BY sort_time DESC
                LIMIT 80
                """
            ).fetchall()
        finally:
            connection.close()

    def _last_lifecycle_event(self, rollout_path: Path) -> tuple[str, int] | None:
        if not rollout_path.is_file():
            return None
        size = rollout_path.stat().st_size
        start = max(0, size - self.tail_bytes)
        last_event: tuple[str, int] | None = None
        marker_bytes = tuple(event.encode("ascii") for event in LIFECYCLE_TYPES)

        with rollout_path.open("rb") as stream:
            stream.seek(start)
            if start:
                stream.readline()  # Discard a possible partial JSON line.
            for raw_line in stream:
                if not any(marker in raw_line for marker in marker_bytes):
                    continue
                try:
                    item = json.loads(raw_line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if item.get("type") != "event_msg":
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                event_type = payload.get("type")
                if event_type not in LIFECYCLE_TYPES:
                    continue
                event_ms = self._timestamp_ms(item.get("timestamp"))
                if event_ms:
                    last_event = str(event_type), event_ms
        return last_event

    @staticmethod
    def _timestamp_ms(value: object) -> int:
        if not isinstance(value, str) or not value:
            return 0
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return 0
        return int(parsed.timestamp() * 1000)

    @staticmethod
    def _clean_name(value: str) -> str:
        return " ".join(value.replace("\x00", "").split()).strip()

    def _short_title(self, value: str, limit: int = 24) -> str:
        cleaned = self._clean_name(value)
        if not cleaned:
            return "未命名任务"
        return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"
