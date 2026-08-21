import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_tasks import CodexTaskCollector


NOW = datetime(2026, 8, 2, 5, 30, tzinfo=timezone.utc).timestamp()


class CodexTaskCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.db = self.home / "state_5.sqlite"
        connection = sqlite3.connect(self.db)
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                rollout_path TEXT NOT NULL,
                title TEXT,
                name TEXT,
                source TEXT,
                thread_source TEXT,
                agent_path TEXT,
                archived INTEGER,
                updated_at INTEGER,
                updated_at_ms INTEGER
            )
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def add_thread(self, thread_id, name, event, timestamp, *, source="vscode", thread_source=None):
        rollout = self.home / f"{thread_id}.jsonl"
        payload = {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {"type": event},
        }
        rollout.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        updated_ms = int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000)
        connection = sqlite3.connect(self.db)
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, NULL, ?, ?, NULL, 0, ?, ?)",
            (thread_id, str(rollout), f"long title for {thread_id}", source, thread_source, updated_ms // 1000, updated_ms),
        )
        connection.commit()
        connection.close()
        if name:
            with (self.home / "session_index.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"id": thread_id, "thread_name": name}, ensure_ascii=False) + "\n")

    def test_returns_running_and_recent_completed_with_short_names(self):
        self.add_thread("running", "动态范围文章撰写", "task_started", "2026-08-02T05:20:00Z")
        self.add_thread("done", "会议记录app", "task_complete", "2026-08-02T05:10:00Z")
        result = CodexTaskCollector(self.home, now=lambda: NOW).collect()
        self.assertTrue(result["ok"])
        self.assertEqual(result["active_count"], 1)
        self.assertEqual([item["name"] for item in result["tasks"]], ["动态范围文章撰写", "会议记录app"])
        self.assertEqual([item["status"] for item in result["tasks"]], ["running", "completed"])

    def test_ignores_old_terminal_events_and_subagents(self):
        self.add_thread("old", "旧任务", "task_complete", "2026-08-02T01:00:00Z")
        self.add_thread(
            "child",
            "子智能体",
            "task_started",
            "2026-08-02T05:25:00Z",
            source='{"subagent":{}}',
            thread_source="subagent",
        )
        result = CodexTaskCollector(self.home, now=lambda: NOW).collect()
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["tasks"], [])

    def test_reads_lifecycle_marker_from_tail_after_large_prefix(self):
        self.add_thread("tail", "尾部任务", "task_started", "2026-08-02T05:29:00Z")
        rollout = self.home / "tail.jsonl"
        original = rollout.read_bytes()
        rollout.write_bytes((b"x" * 2048) + b"\n" + original)
        collector = CodexTaskCollector(self.home, tail_bytes=1024, now=lambda: NOW)
        result = collector.collect()
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["tasks"][0]["name"], "尾部任务")


if __name__ == "__main__":
    unittest.main()
