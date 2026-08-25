#!/usr/bin/env python
"""Local-first daily scratchpad with Markdown and image persistence.

The dashboard writes only under an explicit external data root. It never uses
the repository as a fallback data directory.
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import re
import subprocess
import sys
import threading
import uuid
import webbrowser
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


class SyncConflictError(ValueError):
    """Raised when another device saved a newer copy of the same note."""


def matches_image_signature(content_type: str, body: bytes) -> bool:
    if content_type == "image/png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return body.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP"
    if content_type == "image/gif":
        return body.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/bmp":
        return body.startswith(b"BM")
    return False


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_date(value: str) -> str:
    if not DATE_RE.fullmatch(value):
        raise ValueError("日期格式必须是 YYYY-MM-DD。")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("日期无效。") from exc
    if parsed.isoformat() != value:
        raise ValueError("日期无效。")
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def clean_strokes(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("绘画笔画格式无效。")
    if len(value) > 1000:
        raise ValueError("绘画笔画数量过多。")

    cleaned: list[dict[str, object]] = []
    total_points = 0
    for stroke in value:
        if not isinstance(stroke, dict):
            continue
        tool = str(stroke.get("tool") or "pen")
        if tool not in {"pen", "eraser"}:
            raise ValueError("绘画工具无效。")
        color = str(stroke.get("color") or "#1f7465")
        if not COLOR_RE.fullmatch(color):
            raise ValueError("绘画颜色无效。")
        try:
            width = float(stroke.get("width") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("绘画线宽无效。") from exc
        if not math.isfinite(width) or not 0.0005 <= width <= 0.2:
            raise ValueError("绘画线宽超出范围。")

        raw_points = stroke.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            continue
        if len(raw_points) > 5000:
            raise ValueError("单条笔画点数过多。")
        points: list[list[float]] = []
        for point in raw_points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("绘画坐标无效。")
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError) as exc:
                raise ValueError("绘画坐标无效。") from exc
            if not all(math.isfinite(item) and 0 <= item <= 1 for item in (x, y)):
                raise ValueError("绘画坐标超出范围。")
            points.append([round(x, 6), round(y, 6)])
        total_points += len(points)
        if total_points > 150_000:
            raise ValueError("当天绘画数据过大。")
        cleaned.append(
            {
                "tool": tool,
                "color": color.lower(),
                "width": round(width, 6),
                "points": points,
            }
        )
    return cleaned


def clean_blocks(value: object, day_text: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("记录内容格式无效。")

    blocks: list[dict[str, object]] = []
    asset_prefix = f"assets/{day_text}/"
    for item in value:
        if not isinstance(item, dict):
            continue
        block_type = str(item.get("type") or "")
        if block_type == "text":
            text = str(item.get("text") or "")
            if len(text) > 500_000:
                raise ValueError("单个文本块过长。")
            blocks.append({"type": "text", "text": text})
            continue
        if block_type in {"image", "drawing"}:
            asset = str(item.get("asset") or "").replace("\\", "/")
            if not asset.startswith(asset_prefix):
                raise ValueError("图片路径不属于当前日期。")
            name = asset.removeprefix(asset_prefix)
            if "/" in name or not ASSET_RE.fullmatch(name):
                raise ValueError("图片文件名无效。")
            if block_type == "drawing":
                blocks.append(
                    {
                        "type": "drawing",
                        "asset": asset,
                        "alt": "手绘记录",
                        "strokes": clean_strokes(item.get("strokes")),
                    }
                )
            else:
                blocks.append({"type": "image", "asset": asset, "alt": "现场图片"})

    if len(blocks) > 2000:
        raise ValueError("当天记录块数量过多。")
    if not blocks:
        blocks = [{"type": "text", "text": ""}]
    return blocks


def blocks_to_markdown(day_text: str, blocks: list[dict[str, object]]) -> str:
    lines = [f"# {day_text}", ""]
    for block in blocks:
        if block["type"] == "text":
            text = str(block.get("text", "")).rstrip()
            if text:
                lines.extend([text, ""])
        elif block["type"] in {"image", "drawing"}:
            asset = str(block["asset"]).replace("\\", "/")
            alt = "手绘记录" if block["type"] == "drawing" else "现场图片"
            lines.extend([f"![{alt}](../{asset})", ""])
    return "\n".join(lines).rstrip() + "\n"


def clean_number(value: object, label: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}无效。") from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{label}超出范围。")
    return round(number, 4)


def clean_asset(value: object, day_text: str) -> str:
    asset = str(value or "").replace("\\", "/")
    prefix = f"assets/{day_text}/"
    if not asset.startswith(prefix):
        raise ValueError("图片路径不属于当前日期。")
    name = asset.removeprefix(prefix)
    if "/" in name or not ASSET_RE.fullmatch(name):
        raise ValueError("图片文件名无效。")
    return asset


def clean_canvas_strokes(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("画布笔画格式无效。")
    if len(value) > 2000:
        raise ValueError("画布笔画数量过多。")
    cleaned: list[dict[str, object]] = []
    total_points = 0
    for stroke in value:
        if not isinstance(stroke, dict):
            continue
        stroke_id = str(stroke.get("id") or "")
        if not ID_RE.fullmatch(stroke_id):
            raise ValueError("笔画编号无效。")
        color = str(stroke.get("color") or "#1f7465")
        if not COLOR_RE.fullmatch(color):
            raise ValueError("笔画颜色无效。")
        width = clean_number(stroke.get("width"), "笔画粗细", 0.5, 100)
        raw_points = stroke.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            continue
        if len(raw_points) > 8000:
            raise ValueError("单条笔画点数过多。")
        points: list[list[float]] = []
        for point in raw_points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("笔画坐标无效。")
            x = clean_number(point[0], "笔画横坐标", -10000, 30000)
            y = clean_number(point[1], "笔画纵坐标", -10000, 30000)
            points.append([x, y])
        total_points += len(points)
        if total_points > 250_000:
            raise ValueError("当天画布笔画数据过大。")
        cleaned.append(
            {
                "id": stroke_id,
                "color": color.lower(),
                "width": width,
                "points": points,
            }
        )
    return cleaned


def clean_canvas(value: object, day_text: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("自由画布格式无效。")
    raw_elements = value.get("elements")
    if not isinstance(raw_elements, list) or len(raw_elements) > 2000:
        raise ValueError("画布对象数量无效。")
    elements: list[dict[str, object]] = []
    for item in raw_elements:
        if not isinstance(item, dict):
            continue
        element_id = str(item.get("id") or "")
        if not ID_RE.fullmatch(element_id):
            raise ValueError("画布对象编号无效。")
        element_type = str(item.get("type") or "")
        if element_type not in {"text", "image"}:
            continue
        cleaned: dict[str, object] = {
            "id": element_id,
            "type": element_type,
            "x": clean_number(item.get("x"), "对象横坐标", -10000, 30000),
            "y": clean_number(item.get("y"), "对象纵坐标", -10000, 30000),
            "w": clean_number(item.get("w"), "对象宽度", 40, 10000),
            "h": clean_number(item.get("h"), "对象高度", 30, 10000),
            "z": int(clean_number(item.get("z", 0), "对象层级", -100000, 100000)),
        }
        if element_type == "text":
            text = str(item.get("text") or "")
            if len(text) > 500_000:
                raise ValueError("单个文本框过长。")
            cleaned["text"] = text
        else:
            cleaned["asset"] = clean_asset(item.get("asset"), day_text)
            cleaned["aspect"] = clean_number(item.get("aspect", 1), "图片比例", 0.02, 50)
        elements.append(cleaned)

    camera_value = value.get("camera") if isinstance(value.get("camera"), dict) else {}
    camera = {
        "x": clean_number(camera_value.get("x", 0), "画布视图横坐标", -100000, 100000),
        "y": clean_number(camera_value.get("y", 0), "画布视图纵坐标", -100000, 100000),
        "zoom": clean_number(camera_value.get("zoom", 1), "画布缩放", 0.15, 4),
    }
    preview_asset = str(value.get("preview_asset") or "")
    if preview_asset:
        preview_asset = clean_asset(preview_asset, day_text)
    return {
        "elements": elements,
        "strokes": clean_canvas_strokes(value.get("strokes", [])),
        "camera": camera,
        "preview_asset": preview_asset,
    }


def canvas_to_markdown(day_text: str, canvas: dict[str, object]) -> str:
    lines = [f"# {day_text}", ""]
    preview_asset = str(canvas.get("preview_asset") or "")
    if preview_asset:
        lines.extend([f"![整张画布预览](../{preview_asset})", ""])

    elements = sorted(
        list(canvas.get("elements") or []),
        key=lambda item: (float(item.get("y", 0)), float(item.get("x", 0))),
    )
    texts = [str(item.get("text") or "").strip() for item in elements if item.get("type") == "text"]
    texts = [text for text in texts if text]
    if texts:
        lines.extend(["## 画布文字", ""])
        for text in texts:
            lines.extend([text, ""])

    images = []
    for item in elements:
        if item.get("type") != "image":
            continue
        asset = str(item.get("asset") or "")
        if asset and asset not in images:
            images.append(asset)
    if images:
        lines.extend(["## 画布图片", ""])
        for asset in images:
            lines.extend([f"![画布图片](../{asset})", ""])
    return "\n".join(lines).rstrip() + "\n"


class DailyRecordHandler(BaseHTTPRequestHandler):
    data_root: Path
    state_lock = threading.RLock()
    sync_cache: dict[tuple[str, str], tuple[int, int, str, str]] = {}

    @property
    def daily_root(self) -> Path:
        return self.data_root / "daily"

    @property
    def state_root(self) -> Path:
        return self.data_root / ".state"

    @property
    def assets_root(self) -> Path:
        return self.data_root / "assets"

    def log_message(self, fmt: str, *args: object) -> None:
        if "/api/note-version" in getattr(self, "requestline", ""):
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def sync_metadata(self, day_text: str) -> tuple[str, str]:
        state_path = self.state_root / f"{day_text}.json"
        if not state_path.exists():
            return "", ""
        stat = state_path.stat()
        key = (str(self.data_root), day_text)
        cached = self.sync_cache.get(key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2], cached[3]
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        sync_id = str(payload.get("sync_id") or "")
        updated_at = str(payload.get("updated_at") or "")
        self.sync_cache[key] = (stat.st_mtime_ns, stat.st_size, sync_id, updated_at)
        return sync_id, updated_at

    def cache_sync_metadata(self, day_text: str, sync_id: str, updated_at: str) -> None:
        state_path = self.state_root / f"{day_text}.json"
        stat = state_path.stat()
        self.sync_cache[(str(self.data_root), day_text)] = (
            stat.st_mtime_ns,
            stat.st_size,
            sync_id,
            updated_at,
        )

    def send_payload(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_bytes(payload)
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_payload(
        self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST
    ) -> None:
        self.send_payload({"ok": False, "error": message}, status)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/status":
                self.send_payload(
                    {
                        "ok": True,
                        "data_root": str(self.data_root),
                        "today": date.today().isoformat(),
                    }
                )
                return
            if parsed.path == "/api/note":
                day_text = validate_date(parse_qs(parsed.query).get("date", [""])[0])
                self.handle_get_note(day_text)
                return
            if parsed.path == "/api/note-version":
                day_text = validate_date(parse_qs(parsed.query).get("date", [""])[0])
                self.handle_note_version(day_text)
                return
            if parsed.path == "/api/dates":
                self.handle_dates()
                return
            if parsed.path.startswith("/data/assets/"):
                self.handle_asset(parsed.path.removeprefix("/data/assets/"))
                return
            if parsed.path.startswith("/api/"):
                self.send_error_payload("接口不存在。", HTTPStatus.NOT_FOUND)
                return
            self.handle_static(parsed.path)
        except ValueError as exc:
            self.send_error_payload(str(exc))
        except Exception as exc:
            self.send_error_payload(f"读取失败：{exc}", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/note":
                self.handle_save_note()
                return
            if parsed.path == "/api/image":
                day_text = validate_date(parse_qs(parsed.query).get("date", [""])[0])
                self.handle_image_upload(day_text)
                return
            if parsed.path == "/api/canvas-preview":
                day_text = validate_date(parse_qs(parsed.query).get("date", [""])[0])
                self.handle_canvas_preview(day_text)
                return
            self.send_error_payload("接口不存在。", HTTPStatus.NOT_FOUND)
        except SyncConflictError as exc:
            self.send_error_payload(str(exc), HTTPStatus.CONFLICT)
        except ValueError as exc:
            self.send_error_payload(str(exc))
        except Exception as exc:
            self.send_error_payload(f"保存失败：{exc}", HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_body(self, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError as exc:
            raise ValueError("请求长度无效。") from exc
        if length <= 0:
            raise ValueError("请求内容为空。")
        if length > maximum:
            raise ValueError("请求内容过大。")
        return self.rfile.read(length)

    def handle_static(self, path_text: str) -> None:
        relative = "index.html" if path_text in {"", "/"} else path_text.lstrip("/")
        target = (STATIC_ROOT / relative).resolve()
        static_resolved = STATIC_ROOT.resolve()
        if target != static_resolved and static_resolved not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_get_note(self, day_text: str) -> None:
        state_path = self.state_root / f"{day_text}.json"
        with self.state_lock:
            if state_path.exists():
                payload = json.loads(state_path.read_text(encoding="utf-8"))
                updated_at = str(payload.get("updated_at") or "")
                sync_id = str(payload.get("sync_id") or "")
                if isinstance(payload.get("canvas"), dict):
                    canvas = clean_canvas(payload.get("canvas"), day_text)
                    blocks = None
                else:
                    canvas = None
                    blocks = clean_blocks(payload.get("blocks"), day_text)
            else:
                canvas = None
                blocks = [{"type": "text", "text": ""}]
                updated_at = ""
                sync_id = ""
        response = {
            "ok": True,
            "date": day_text,
            "updated_at": updated_at,
            "sync_id": sync_id,
        }
        if canvas is not None:
            response["canvas"] = canvas
        else:
            response["blocks"] = blocks
        self.send_payload(response)

    def handle_note_version(self, day_text: str) -> None:
        with self.state_lock:
            sync_id, updated_at = self.sync_metadata(day_text)
        self.send_payload(
            {
                "ok": True,
                "date": day_text,
                "sync_id": sync_id,
                "updated_at": updated_at,
            }
        )

    def handle_dates(self) -> None:
        dates = set()
        if self.state_root.exists():
            for path in self.state_root.glob("20??-??-??.json"):
                if DATE_RE.fullmatch(path.stem):
                    dates.add(path.stem)
        if self.daily_root.exists():
            for path in self.daily_root.glob("20??-??-??.md"):
                if DATE_RE.fullmatch(path.stem):
                    dates.add(path.stem)
        self.send_payload({"ok": True, "dates": sorted(dates, reverse=True)[:90]})

    def handle_save_note(self) -> None:
        raw = self.read_body(MAX_JSON_BYTES)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("记录内容不是有效 JSON。") from exc
        if not isinstance(payload, dict):
            raise ValueError("记录内容格式无效。")
        day_text = validate_date(str(payload.get("date") or ""))
        base_sync_id = str(payload.get("base_sync_id") or "")
        source_client_id = str(payload.get("source_client_id") or "")
        if source_client_id and not ID_RE.fullmatch(source_client_id):
            raise ValueError("同步设备编号无效。")
        updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        sync_id = uuid.uuid4().hex
        if isinstance(payload.get("canvas"), dict):
            canvas = clean_canvas(payload.get("canvas"), day_text)
            state = {
                "version": 2,
                "date": day_text,
                "updated_at": updated_at,
                "sync_id": sync_id,
                "source_client_id": source_client_id,
                "canvas": canvas,
            }
            markdown = canvas_to_markdown(day_text, canvas)
        else:
            blocks = clean_blocks(payload.get("blocks"), day_text)
            state = {
                "version": 1,
                "date": day_text,
                "updated_at": updated_at,
                "sync_id": sync_id,
                "source_client_id": source_client_id,
                "blocks": blocks,
            }
            markdown = blocks_to_markdown(day_text, blocks)

        state_path = self.state_root / f"{day_text}.json"
        with self.state_lock:
            current_sync_id = ""
            if state_path.exists():
                current_payload = json.loads(state_path.read_text(encoding="utf-8"))
                current_sync_id = str(current_payload.get("sync_id") or "")
            if base_sync_id and current_sync_id and base_sync_id != current_sync_id:
                raise SyncConflictError("另一台设备刚刚更新了这一天，请刷新后再继续编辑。")
            atomic_write(
                state_path,
                json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
            )
            atomic_write(self.daily_root / f"{day_text}.md", markdown.encode("utf-8"))
            self.cache_sync_metadata(day_text, sync_id, updated_at)
        self.send_payload(
            {
                "ok": True,
                "date": day_text,
                "updated_at": updated_at,
                "sync_id": sync_id,
            }
        )

    def handle_image_upload(self, day_text: str) -> None:
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        extension = IMAGE_EXTENSIONS.get(content_type)
        if not extension:
            raise ValueError("仅支持 PNG、JPEG、WebP、GIF 或 BMP 图片。")
        body = self.read_body(MAX_IMAGE_BYTES)
        if not matches_image_signature(content_type, body):
            raise ValueError("剪贴板内容不是有效图片。")
        name = f"{datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:10]}{extension}"
        target = self.assets_root / day_text / name
        atomic_write(target, body)
        asset = f"assets/{day_text}/{name}"
        self.send_payload({"ok": True, "asset": asset, "url": f"/data/{asset}"})

    def handle_canvas_preview(self, day_text: str) -> None:
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "image/png":
            raise ValueError("画布预览必须是 PNG 图片。")
        body = self.read_body(MAX_IMAGE_BYTES)
        if not matches_image_signature(content_type, body):
            raise ValueError("画布预览不是有效 PNG 图片。")
        name = "canvas-preview.png"
        target = self.assets_root / day_text / name
        atomic_write(target, body)
        asset = f"assets/{day_text}/{name}"
        self.send_payload({"ok": True, "asset": asset, "url": f"/data/{asset}"})

    def handle_asset(self, relative: str) -> None:
        parts = Path(unquote(relative)).parts
        if len(parts) != 2:
            raise ValueError("图片路径无效。")
        day_text = validate_date(parts[0])
        name = parts[1]
        if not ASSET_RE.fullmatch(name):
            raise ValueError("图片文件名无效。")
        target = (self.assets_root / day_text / name).resolve()
        assets_resolved = self.assets_root.resolve()
        if assets_resolved not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地每日记录草稿面板。")
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DAILY_DRAFT_DATA_ROOT"),
        help="外部记录目录；默认读取 DAILY_DRAFT_DATA_ROOT。",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument(
        "--share-tailscale",
        action="store_true",
        help="同时监听本机的 Tailscale IPv4 地址，供已授权手机访问。",
    )
    return parser.parse_args()


def tailscale_ipv4() -> str:
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")


def main() -> int:
    args = parse_args()
    if not args.data_root:
        print(
            "ERROR: 请设置 DAILY_DRAFT_DATA_ROOT，或传入 --data-root。不会默认写入代码仓库。",
            file=sys.stderr,
        )
        return 2

    data_root = Path(args.data_root).expanduser().resolve()
    repository_root = ROOT.parents[1].resolve()
    if data_root == repository_root or repository_root in data_root.parents:
        print(f"ERROR: 记录目录不能位于代码仓库内：{data_root}", file=sys.stderr)
        return 2
    data_root.mkdir(parents=True, exist_ok=True)
    for child in (data_root / "daily", data_root / "assets", data_root / ".state"):
        child.mkdir(parents=True, exist_ok=True)

    handler = type("ConfiguredDailyRecordHandler", (DailyRecordHandler,), {"data_root": data_root})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    shared_server = None
    shared_thread = None
    share_url = ""
    if args.share_tailscale:
        share_ip = tailscale_ipv4()
        if share_ip and share_ip != args.host:
            try:
                shared_server = ThreadingHTTPServer((share_ip, args.port), handler)
                shared_thread = threading.Thread(target=shared_server.serve_forever, daemon=True)
                shared_thread.start()
                share_url = f"http://{share_ip}:{args.port}/"
            except OSError as exc:
                print(f"WARNING: Tailscale 手机入口启动失败：{exc}", file=sys.stderr)
        else:
            print("WARNING: 没有检测到 Tailscale IPv4 地址，仅开放本机访问。", file=sys.stderr)

    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{browser_host}:{args.port}/"
    print(f"每日记录面板：{url}")
    if share_url:
        print(f"手机访问地址（需开启 Tailscale）：{share_url}")
    print(f"记录目录：{data_root}")
    print("按 Ctrl+C 停止。")
    if args.open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止。")
    finally:
        if shared_server is not None:
            shared_server.shutdown()
            shared_server.server_close()
        if shared_thread is not None:
            shared_thread.join(timeout=2)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
