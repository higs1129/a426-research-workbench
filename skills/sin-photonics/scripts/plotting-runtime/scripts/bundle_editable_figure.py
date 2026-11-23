"""Bundle a project-specific scientific figure shell into one offline HTML file.

This script does not choose traces, scales, annotations, or scientific meaning. The
project adapter owns those decisions. It only embeds the shared interaction runtime,
one fixed delivery profile, authoritative JSON data, and the adapter JavaScript.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = SKILL_ROOT / "assets" / "editable-figure-runtime.js"
PROFILE_PATH = SKILL_ROOT / "assets" / "style-profiles.json"

MARKERS = {
    "runtime": "<!-- SCIENTIFIC_FIGURE_RUNTIME -->",
    "adapter": "<!-- SCIENTIFIC_FIGURE_ADAPTER -->",
    "data": "<!-- SCIENTIFIC_FIGURE_DATA -->",
    "profile": "<!-- SCIENTIFIC_FIGURE_PROFILE -->",
}
RUNTIME_VERSION = "1.0.0"


def read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise SystemExit(f"{label} not found: {path}") from error


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(read_text(path, label))
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{label} is not valid JSON: {path}:{error.lineno}:{error.colno}"
        ) from error


def script_safe_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def script_safe_code(value: str) -> str:
    return re.sub(r"</script", r"<\\/script", value, flags=re.IGNORECASE)


def replace_once(shell: str, marker: str, replacement: str, label: str) -> str:
    count = shell.count(marker)
    if count != 1:
        raise SystemExit(
            f"Figure shell must contain exactly one {label} marker {marker!r}; found {count}."
        )
    return shell.replace(marker, replacement, 1)


def load_profile(profile_id: str) -> dict[str, Any]:
    profiles = read_json(PROFILE_PATH, "Style profile file")
    if profile_id not in profiles:
        available = ", ".join(sorted(profiles))
        raise SystemExit(f"Unknown profile {profile_id!r}; choose one of: {available}")
    return {"id": profile_id, **profiles[profile_id]}


def bundle_text(
    *,
    shell: str,
    adapter: str,
    data: Any,
    profile_id: str,
) -> str:
    """Bundle already-loaded content without forcing temporary project files."""

    runtime = read_text(RUNTIME_PATH, "Shared interaction runtime")
    profile = load_profile(profile_id)

    shell = replace_once(
        shell,
        MARKERS["runtime"],
        f'<script data-sf-runtime-version="{RUNTIME_VERSION}">\n'
        f"{script_safe_code(runtime)}\n</script>",
        "runtime",
    )
    shell = replace_once(
        shell,
        MARKERS["profile"],
        '<script id="scientific-figure-profile" type="application/json">'
        f"{script_safe_json(profile)}</script>",
        "profile",
    )
    shell = replace_once(
        shell,
        MARKERS["data"],
        '<script id="scientific-figure-data" type="application/json">'
        f"{script_safe_json(data)}</script>",
        "data",
    )
    shell = replace_once(
        shell,
        MARKERS["adapter"],
        f"<script>\n{script_safe_code(adapter)}\n</script>",
        "adapter",
    )
    return shell


def bundle(
    *,
    shell_path: Path,
    adapter_path: Path,
    data_path: Path,
    profile_id: str,
) -> str:
    return bundle_text(
        shell=read_text(shell_path, "Figure shell"),
        adapter=read_text(adapter_path, "Figure adapter"),
        data=read_json(data_path, "Figure data"),
        profile_id=profile_id,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle an editable scientific figure into self-contained HTML."
    )
    parser.add_argument("--shell", type=Path, required=True, help="Project HTML shell")
    parser.add_argument(
        "--adapter", type=Path, required=True, help="Project JavaScript adapter"
    )
    parser.add_argument("--data", type=Path, required=True, help="Authoritative JSON data")
    parser.add_argument(
        "--profile-id",
        required=True,
        help="One fixed profile id from assets/style-profiles.json",
    )
    parser.add_argument("--output", type=Path, required=True, help="Final HTML path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    html = bundle(
        shell_path=args.shell.resolve(),
        adapter_path=args.adapter.resolve(),
        data_path=args.data.resolve(),
        profile_id=args.profile_id,
    )
    output.write_text(html, encoding="utf-8", newline="\n")
    print(output)


if __name__ == "__main__":
    main()
