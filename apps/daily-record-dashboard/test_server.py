from __future__ import annotations

import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from server import DailyRecordHandler


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class DashboardServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_root = Path(self.temporary.name)
        handler = type(
            "TestDailyRecordHandler",
            (DailyRecordHandler,),
            {"data_root": self.data_root},
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request_json(
        self, path: str, *, method: str = "GET", payload: object | None = None, content_type: str = "application/json"
    ) -> dict[str, object]:
        body = None
        if payload is not None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_note_round_trip_and_markdown(self) -> None:
        uploaded = self.request_json(
            "/api/image?date=2026-08-20",
            method="POST",
            payload=ONE_PIXEL_PNG,
            content_type="image/png",
        )
        asset = str(uploaded["asset"])
        saved = self.request_json(
            "/api/note",
            method="POST",
            payload={
                "date": "2026-08-20",
                "blocks": [
                    {"type": "text", "text": "今天完成了测试。"},
                    {"type": "image", "asset": asset},
                    {
                        "type": "drawing",
                        "asset": asset,
                        "strokes": [
                            {
                                "tool": "pen",
                                "color": "#1f7465",
                                "width": 0.01,
                                "points": [[0.1, 0.2], [0.4, 0.5]],
                            }
                        ],
                    },
                    {"type": "text", "text": "图片之后继续记录。"},
                ],
            },
        )
        self.assertTrue(saved["ok"])

        loaded = self.request_json("/api/note?date=2026-08-20")
        self.assertEqual(len(loaded["blocks"]), 4)
        self.assertEqual(loaded["blocks"][2]["type"], "drawing")
        self.assertEqual(len(loaded["blocks"][2]["strokes"]), 1)
        markdown = (self.data_root / "daily" / "2026-08-20.md").read_text(encoding="utf-8")
        self.assertIn("今天完成了测试。", markdown)
        self.assertIn(f"![现场图片](../{asset})", markdown)
        self.assertIn(f"![手绘记录](../{asset})", markdown)
        self.assertIn("图片之后继续记录。", markdown)
        self.assertTrue((self.data_root / asset).is_file())

    def test_dates_are_listed_newest_first(self) -> None:
        for day_text in ("2026-08-18", "2026-08-20", "2026-08-19"):
            self.request_json(
                "/api/note",
                method="POST",
                payload={"date": day_text, "blocks": [{"type": "text", "text": day_text}]},
            )
        payload = self.request_json("/api/dates")
        self.assertEqual(payload["dates"], ["2026-08-20", "2026-08-19", "2026-08-18"])

    def test_free_canvas_round_trip_preview_and_markdown(self) -> None:
        uploaded = self.request_json(
            "/api/image?date=2026-08-20",
            method="POST",
            payload=ONE_PIXEL_PNG,
            content_type="image/png",
        )
        preview = self.request_json(
            "/api/canvas-preview?date=2026-08-20",
            method="POST",
            payload=ONE_PIXEL_PNG,
            content_type="image/png",
        )
        canvas = {
            "elements": [
                {
                    "id": "text-1",
                    "type": "text",
                    "x": 120,
                    "y": 80,
                    "w": 420,
                    "h": 160,
                    "z": 2,
                    "text": "自由画布中的文字。",
                },
                {
                    "id": "image-1",
                    "type": "image",
                    "x": 620,
                    "y": 140,
                    "w": 500,
                    "h": 300,
                    "z": 3,
                    "asset": uploaded["asset"],
                    "aspect": 5 / 3,
                },
            ],
            "strokes": [
                {
                    "id": "stroke-1",
                    "color": "#1f7465",
                    "width": 6,
                    "points": [[100, 100], [200, 180], [300, 150]],
                }
            ],
            "camera": {"x": 40, "y": 20, "zoom": 0.9},
            "preview_asset": preview["asset"],
        }
        self.request_json(
            "/api/note",
            method="POST",
            payload={"date": "2026-08-20", "canvas": canvas},
        )

        loaded = self.request_json("/api/note?date=2026-08-20")
        self.assertNotIn("blocks", loaded)
        self.assertEqual(len(loaded["canvas"]["elements"]), 2)
        self.assertEqual(len(loaded["canvas"]["strokes"]), 1)
        self.assertEqual(loaded["canvas"]["camera"]["zoom"], 0.9)
        markdown = (self.data_root / "daily" / "2026-08-20.md").read_text(encoding="utf-8")
        self.assertIn("![整张画布预览]", markdown)
        self.assertIn("自由画布中的文字。", markdown)
        self.assertIn(f"![画布图片](../{uploaded['asset']})", markdown)
        saved_state = json.loads(
            (self.data_root / ".state" / "2026-08-20.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved_state["version"], 2)

    def test_sync_version_changes_and_rejects_stale_save(self) -> None:
        first = self.request_json(
            "/api/note",
            method="POST",
            payload={
                "date": "2026-08-20",
                "blocks": [{"type": "text", "text": "手机第一笔"}],
                "source_client_id": "phone-client",
            },
        )
        first_sync_id = str(first["sync_id"])
        version = self.request_json("/api/note-version?date=2026-08-20")
        self.assertEqual(version["sync_id"], first_sync_id)

        second = self.request_json(
            "/api/note",
            method="POST",
            payload={
                "date": "2026-08-20",
                "blocks": [{"type": "text", "text": "电脑已收到"}],
                "base_sync_id": first_sync_id,
                "source_client_id": "desktop-client",
            },
        )
        self.assertNotEqual(second["sync_id"], first_sync_id)

        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request_json(
                "/api/note",
                method="POST",
                payload={
                    "date": "2026-08-20",
                    "blocks": [{"type": "text", "text": "过期副本"}],
                    "base_sync_id": first_sync_id,
                    "source_client_id": "phone-client",
                },
            )
        self.assertEqual(raised.exception.code, 409)
        loaded = self.request_json("/api/note?date=2026-08-20")
        self.assertEqual(loaded["blocks"][0]["text"], "电脑已收到")


if __name__ == "__main__":
    unittest.main()
