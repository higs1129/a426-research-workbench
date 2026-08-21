from __future__ import annotations

import argparse
import base64
import html
import json
import math
import re
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CavityRow:
    die: str
    cavity: int
    max_q0_m: float | None
    q_polarization: str | None
    best_sensitivity_upa: float | None
    sensitivity_polarization: str | None
    noise_dbm_per_hz: float | None
    response_dbm_per_pa2: float | None
    response_bandwidth_khz: float | None
    covered: bool


RADIUS_BY_DIE = {
    "die_1_1": 125,
    "die_1_2": 125,
    "die_1_3": 105,
    "die_1_4": 105,
    "die_2_1": 85,
    "die_2_2": 85,
    "die_2_3": 65,
    "die_2_4": 65,
}

DIE_ORDER = list(RADIUS_BY_DIE)

RADIUS_COLORS = {
    125: "#176b87",
    105: "#d06b32",
    85: "#6a7f3f",
    65: "#7657a8",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained Chinese monthly work summary."
    )
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--weekly-report", type=Path, required=True)
    parser.add_argument("--photoacoustic-root", type=Path, required=True)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing report.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_rows(weekly_report: Path) -> list[CavityRow]:
    report = read_text(weekly_report)
    match = re.search(r"const\s+DATA\s*=\s*(\[[\s\S]*?\])\.map\(", report)
    if not match:
        raise RuntimeError(f"Cannot find const DATA in {weekly_report}")
    raw_rows = json.loads(match.group(1))
    rows: list[CavityRow] = []
    for raw in raw_rows:
        if len(raw) != 10:
            raise RuntimeError(f"Unexpected weekly DATA row: {raw!r}")
        rows.append(
            CavityRow(
                die=str(raw[0]),
                cavity=int(raw[1]),
                max_q0_m=None if raw[2] is None else float(raw[2]),
                q_polarization=raw[3],
                best_sensitivity_upa=None if raw[4] is None else float(raw[4]),
                sensitivity_polarization=raw[5],
                noise_dbm_per_hz=None if raw[6] is None else float(raw[6]),
                response_dbm_per_pa2=None if raw[7] is None else float(raw[7]),
                response_bandwidth_khz=None if raw[8] is None else float(raw[8]),
                covered=bool(raw[9]),
            )
        )
    return rows


def metric_from_weekly_report(report_text: str, label: str) -> int | None:
    pattern = (
        r'<div class="metric"><strong>(\d+)</strong>'
        r"<span>" + re.escape(label) + r"</span></div>"
    )
    match = re.search(pattern, report_text)
    return int(match.group(1)) if match else None


def median(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and math.isfinite(value)]
    return statistics.median(clean) if clean else None


def fmt(value: float | None, digits: int = 2, suffix: str = "") -> str:
    if value is None or not math.isfinite(value):
        return "未测"
    return f"{value:.{digits}f}{suffix}"


def image_data_uri(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix)
    if mime is None:
        raise ValueError(f"Unsupported embedded image type: {path}")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def cavity_path(campaign_root: Path, die: str, cavity: int) -> Path:
    return campaign_root / "results" / "chip_7" / die / f"cavity_{cavity}"


def find_latest_sensitivity_figure(cavity_dir: Path) -> Path:
    candidates: list[tuple[str, Path]] = []
    for subdir in ("sensitivity", "sensitivity'"):
        latest = cavity_dir / subdir / "latest.json"
        if not latest.exists():
            continue
        payload = json.loads(read_text(latest))
        figure_rel = payload.get("figure_png")
        if not figure_rel:
            continue
        figure = cavity_dir / Path(str(figure_rel))
        if figure.exists():
            candidates.append((str(payload.get("updated_at", "")), figure))
    if not candidates:
        raise FileNotFoundError(f"No latest sensitivity figure under {cavity_dir}")
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def find_figure(cavity_dir: Path) -> Path:
    figures = sorted(
        [
            item
            for item in (cavity_dir / "figure").glob("*")
            if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ],
        key=lambda item: item.name,
    )
    if not figures:
        raise FileNotFoundError(f"No cavity morphology image under {cavity_dir / 'figure'}")
    return figures[-1]


def bar_chart_svg(rows: list[CavityRow]) -> str:
    per_die: list[tuple[str, int, float | None, float | None]] = []
    for die in DIE_ORDER:
        die_rows = [row for row in rows if row.die == die]
        per_die.append(
            (
                die,
                RADIUS_BY_DIE[die],
                median(row.max_q0_m for row in die_rows),
                median(row.best_sensitivity_upa for row in die_rows),
            )
        )

    width = 1040
    height = 500
    label_x = 122
    q_x0, q_width = 190, 285
    s_x0, s_width = 650, 285
    top = 84
    step = 47
    q_values = [item[2] for item in per_die if item[2] is not None]
    s_values = [item[3] for item in per_die if item[3] is not None]
    q_max = max(q_values) * 1.08
    s_max = max(s_values) * 1.08
    parts = [
        f'<svg class="summary-chart" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="die-chart-title die-chart-desc">',
        '<title id="die-chart-title">各 die 的中位 Q0 与中位灵敏度</title>',
        '<desc id="die-chart-desc">左侧为中位 Q0，越长越高；右侧为中位灵敏度，越短越好。'
        "die_2_1 无正式测量，保留为空。</desc>",
        '<text x="190" y="34" class="svg-title">各 die 的稳健水平</text>',
        '<text x="190" y="59" class="svg-note">中位 Q0（M）· 越长越高</text>',
        '<text x="650" y="59" class="svg-note">中位灵敏度（µPa/√Hz）· 越短越好</text>',
    ]
    for index, (die, radius, q_value, sensitivity) in enumerate(per_die):
        y = top + index * step
        color = RADIUS_COLORS[radius]
        parts.extend(
            [
                f'<text x="{label_x}" y="{y + 16}" text-anchor="end" class="svg-label">'
                f"{html.escape(die)}</text>",
                f'<text x="{label_x + 12}" y="{y + 16}" class="svg-radius">{radius} µm</text>',
                f'<line x1="{q_x0}" y1="{y + 22}" x2="{s_x0 + s_width}" y2="{y + 22}" '
                'stroke="#e7e2d8" stroke-width="1"/>',
            ]
        )
        if q_value is None:
            parts.append(
                f'<text x="{q_x0}" y="{y + 16}" class="svg-empty">无正式数据</text>'
            )
        else:
            q_bar = q_width * q_value / q_max
            s_bar = s_width * sensitivity / s_max if sensitivity is not None else 0
            parts.extend(
                [
                    f'<rect x="{q_x0}" y="{y}" width="{q_bar:.1f}" height="24" rx="6" '
                    f'fill="{color}" opacity=".88"/>',
                    f'<text x="{q_x0 + q_bar + 8:.1f}" y="{y + 17}" class="svg-value">'
                    f"{q_value:.2f}</text>",
                ]
            )
            if sensitivity is not None:
                parts.extend(
                    [
                        f'<rect x="{s_x0}" y="{y}" width="{s_bar:.1f}" height="24" rx="6" '
                        f'fill="{color}" opacity=".62"/>',
                        f'<text x="{s_x0 + s_bar + 8:.1f}" y="{y + 17}" class="svg-value">'
                        f"{sensitivity:.2f}</text>",
                    ]
                )
    parts.append("</svg>")
    return "".join(parts)


def gap_table(rows: list[CavityRow]) -> str:
    table_rows: list[str] = []
    for die in DIE_ORDER:
        die_rows = [row for row in rows if row.die == die]
        cells: list[str] = []
        for group in range(3):
            lo = group * 3 + 1
            hi = lo + 2
            group_rows = [row for row in die_rows if lo <= row.cavity <= hi]
            q_value = median(row.max_q0_m for row in group_rows)
            s_value = median(row.best_sensitivity_upa for row in group_rows)
            cells.append(
                "<td>"
                f'<span class="cell-primary">{fmt(q_value, 2)}</span>'
                f'<span class="cell-secondary">{fmt(s_value, 2)} µPa/√Hz</span>'
                "</td>"
            )
        table_rows.append(
            "<tr>"
            f"<th>{html.escape(die)}<small>{RADIUS_BY_DIE[die]} µm</small></th>"
            + "".join(cells)
            + "</tr>"
        )
    return "".join(table_rows)


def ball_lens_svg() -> str:
    return """
<svg class="ball-lens" viewBox="0 0 1000 340" role="img"
     aria-labelledby="optic-title-month optic-desc-month">
  <title id="optic-title-month">单模光纤、无芯扩束段和球形端面的轴向结构示意</title>
  <desc id="optic-desc-month">左侧单模光纤输出窄高斯光束，光束在无芯石英段内扩展，
  经球形石英空气界面折射后在空气中形成光腰。</desc>
  <defs>
    <marker id="month-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#176b87"/>
    </marker>
    <marker id="month-dim" markerWidth="8" markerHeight="8" refX="4" refY="4"
            orient="auto-start-reverse">
      <path d="M0,0 L8,4 L0,8 z" fill="#68726f"/>
    </marker>
    <clipPath id="month-glass">
      <path d="M50 105 H650 A95 95 0 0 1 650 295 H50 Z"/>
    </clipPath>
  </defs>
  <rect x="50" y="105" width="610" height="190" rx="18"
        fill="#dce9e5" stroke="#84aaa3" stroke-width="2"/>
  <circle cx="650" cy="200" r="95" fill="#dce9e5" stroke="#84aaa3" stroke-width="2"/>
  <rect x="50" y="192" width="265" height="16" rx="8" fill="#345e9d" opacity=".85"/>
  <line x1="315" y1="100" x2="315" y2="300" stroke="#1f2927" stroke-width="2"
        stroke-dasharray="6 5"/>
  <path d="M315 193 C420 185,525 157,650 126" fill="none" stroke="#176b87"
        stroke-width="4" clip-path="url(#month-glass)"/>
  <path d="M315 207 C420 215,525 243,650 274" fill="none" stroke="#176b87"
        stroke-width="4" clip-path="url(#month-glass)"/>
  <line x1="315" y1="200" x2="935" y2="200" stroke="#a7afad" stroke-width="1.5"
        stroke-dasharray="8 7"/>
  <path d="M650 126 Q788 166 918 197" fill="none" stroke="#176b87" stroke-width="4"/>
  <path d="M650 274 Q788 234 918 203" fill="none" stroke="#176b87" stroke-width="4"/>
  <ellipse cx="920" cy="200" rx="5" ry="24" fill="#d06b32" opacity=".9"/>
  <path d="M925 200 Q954 190 975 176" fill="none" stroke="#176b87" stroke-width="2"
        marker-end="url(#month-arrow)"/>
  <path d="M925 200 Q954 210 975 224" fill="none" stroke="#176b87" stroke-width="2"
        marker-end="url(#month-arrow)"/>
  <line x1="315" y1="320" x2="745" y2="320" stroke="#68726f" stroke-width="1.5"
        marker-start="url(#month-dim)" marker-end="url(#month-dim)"/>
  <line x1="745" y1="320" x2="920" y2="320" stroke="#d06b32" stroke-width="1.5"
        marker-start="url(#month-dim)" marker-end="url(#month-dim)"/>
  <line x1="315" y1="303" x2="315" y2="330" stroke="#68726f"/>
  <line x1="745" y1="285" x2="745" y2="330" stroke="#68726f"/>
  <line x1="920" y1="220" x2="920" y2="330" stroke="#68726f"/>
  <text x="128" y="82" font-size="22" font-weight="700" fill="#1f2927">CS460 / 460-HP</text>
  <text x="125" y="222" font-size="16" fill="#fff">基模纤芯</text>
  <text x="410" y="82" font-size="22" font-weight="700" fill="#1f2927">无芯石英扩束段</text>
  <text x="291" y="92" font-size="15" fill="#68726f">熔接面</text>
  <text x="642" y="80" font-size="18" font-weight="700" fill="#1f2927">熔融球形端面</text>
  <text x="805" y="104" font-size="17" fill="#68726f">空气</text>
  <text x="505" y="315" font-size="18" font-weight="700" fill="#1f2927">Lᵥ：熔接面 → 顶点</text>
  <text x="790" y="315" font-size="18" font-weight="700" fill="#b45023">WD：顶点 → 光腰</text>
</svg>
""".strip()


def program_flow_svg() -> str:
    return """
<svg class="program-flow" viewBox="0 0 1200 330" role="img"
     aria-labelledby="program-title-month program-desc-month">
  <title id="program-title-month">本月微腔测量程序工作流</title>
  <desc id="program-desc-month">程序从测量目录和面板状态记忆开始，依次完成大扫采集与旧数据归档、
  模式家族交叉识别和偏振整理、锁模及 Red Pitaya 监控，最终输出灵敏度、声压、Card 和标签。</desc>
  <defs>
    <marker id="program-arrow-month" markerWidth="10" markerHeight="10"
            refX="8" refY="5" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#176b87"/>
    </marker>
  </defs>
  <text x="40" y="42" class="svg-title">从现场采集到可比较结果</text>
  <text x="40" y="70" class="svg-note">同一腔目录贯穿采集、分析、锁模、声学换算与结果留存</text>

  <g transform="translate(35 105)">
    <rect width="190" height="142" rx="16" fill="#e4f0f3" stroke="#176b87" stroke-width="2"/>
    <circle cx="28" cy="29" r="16" fill="#176b87"/>
    <text x="28" y="35" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">1</text>
    <text x="20" y="70" font-size="18" font-weight="800" fill="#1f2927">路径与面板记忆</text>
    <text x="20" y="98" font-size="14" fill="#68726f">从 die/cavity 进入后</text>
    <text x="20" y="121" font-size="14" fill="#68726f">同步目录、功率和选项</text>
  </g>
  <line x1="232" y1="176" x2="265" y2="176" stroke="#176b87" stroke-width="3"
        marker-end="url(#program-arrow-month)"/>

  <g transform="translate(270 105)">
    <rect width="190" height="142" rx="16" fill="#fff" stroke="#84aaa3" stroke-width="2"/>
    <circle cx="28" cy="29" r="16" fill="#47755a"/>
    <text x="28" y="35" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">2</text>
    <text x="20" y="70" font-size="18" font-weight="800" fill="#1f2927">大扫与安全归档</text>
    <text x="20" y="98" font-size="14" fill="#68726f">200 kSa/s 采集、门控</text>
    <text x="20" y="121" font-size="14" fill="#68726f">旧数据按创建日期打包</text>
  </g>
  <line x1="467" y1="176" x2="500" y2="176" stroke="#176b87" stroke-width="3"
        marker-end="url(#program-arrow-month)"/>

  <g transform="translate(505 105)">
    <rect width="190" height="142" rx="16" fill="#fff" stroke="#84aaa3" stroke-width="2"/>
    <circle cx="28" cy="29" r="16" fill="#47755a"/>
    <text x="28" y="35" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">3</text>
    <text x="20" y="70" font-size="18" font-weight="800" fill="#1f2927">家族、交叉与偏振</text>
    <text x="20" y="98" font-size="14" fill="#68726f">平滑全局跟踪交叉模式</text>
    <text x="20" y="121" font-size="14" fill="#68726f">整理 Q/Q′ 与 TE/TM</text>
  </g>
  <line x1="702" y1="176" x2="735" y2="176" stroke="#176b87" stroke-width="3"
        marker-end="url(#program-arrow-month)"/>

  <g transform="translate(740 105)">
    <rect width="190" height="142" rx="16" fill="#fff" stroke="#84aaa3" stroke-width="2"/>
    <circle cx="28" cy="29" r="16" fill="#47755a"/>
    <text x="28" y="35" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">4</text>
    <text x="20" y="70" font-size="18" font-weight="800" fill="#1f2927">锁模与 RP 监控</text>
    <text x="20" y="98" font-size="14" fill="#68726f">常驻 TOPTICA、租约</text>
    <text x="20" y="121" font-size="14" fill="#68726f">PID 跳转与浮窗监控</text>
  </g>
  <line x1="937" y1="176" x2="970" y2="176" stroke="#176b87" stroke-width="3"
        marker-end="url(#program-arrow-month)"/>

  <g transform="translate(975 105)">
    <rect width="190" height="142" rx="16" fill="#f9ebe3" stroke="#d06b32" stroke-width="2"/>
    <circle cx="28" cy="29" r="16" fill="#d06b32"/>
    <text x="28" y="35" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">5</text>
    <text x="20" y="70" font-size="18" font-weight="800" fill="#1f2927">结果与挑选</text>
    <text x="20" y="98" font-size="14" fill="#68726f">灵敏度、声压、Card</text>
    <text x="20" y="121" font-size="14" fill="#68726f">颜色标签、备注与对比</text>
  </g>
  <text x="600" y="292" text-anchor="middle" font-size="15" font-weight="700" fill="#176b87">
    目标：减少重复输入，让每次测量都能追溯到同一物理腔和同一组原始证据
  </text>
</svg>
""".strip()


def generate_report(args: argparse.Namespace) -> str:
    weekly_text = read_text(args.weekly_report)
    rows = load_rows(args.weekly_report)

    q_rows = [row for row in rows if row.max_q0_m is not None]
    sensitivity_rows = [row for row in rows if row.best_sensitivity_upa is not None]
    best_q = max(q_rows, key=lambda row: row.max_q0_m or -math.inf)
    best_sensitivity = min(
        sensitivity_rows,
        key=lambda row: row.best_sensitivity_upa or math.inf,
    )
    sensitivity_results = metric_from_weekly_report(weekly_text, "周内灵敏度结果")
    if sensitivity_results is None:
        sensitivity_results = len(sensitivity_rows)

    q_figure = (
        cavity_path(args.campaign_root, best_q.die, best_q.cavity)
        / "Q"
        / "q_trend.png"
    )
    sensitivity_figure = find_latest_sensitivity_figure(
        cavity_path(args.campaign_root, best_sensitivity.die, best_sensitivity.cavity)
    )
    morphology_figure = find_figure(
        cavity_path(args.campaign_root, "die_1_4", 5)
    )
    for required in (q_figure, sensitivity_figure, morphology_figure):
        if not required.exists():
            raise FileNotFoundError(required)

    q_uri = image_data_uri(q_figure)
    sensitivity_uri = image_data_uri(sensitivity_figure)
    morphology_uri = image_data_uri(morphology_figure)

    q_pol_count = {
        pol: sum(1 for row in q_rows if row.q_polarization == pol)
        for pol in ("TE", "TM")
    }
    s_pol_count = {
        pol: sum(
            1 for row in sensitivity_rows if row.sensitivity_polarization == pol
        )
        for pol in ("TE", "TM")
    }

    as_of = date.fromisoformat(args.as_of)
    daily_files = sorted((args.campaign_root / "daily").glob(f"{args.month}-*.md"))
    photo_daily = sorted((args.photoacoustic_root / "daily").glob(f"{args.month}-*.md"))
    source_days = sorted(
        {path.stem[:10] for path in [*daily_files, *photo_daily] if len(path.stem) >= 10}
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>2026 年 7 月工作总结（截至 {as_of.month} 月 {as_of.day} 日）</title>
  <style>
    :root {{
      --paper: #f4f1e9;
      --surface: #fffdf8;
      --ink: #1f2927;
      --muted: #68726f;
      --line: #ddd7ca;
      --blue: #176b87;
      --blue-soft: #e4f0f3;
      --orange: #d06b32;
      --orange-soft: #f9ebe3;
      --green: #47755a;
      --red: #a64737;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.66;
    }}
    main {{
      width: min(1320px, calc(100% - 32px));
      margin: 24px auto;
      padding: clamp(24px, 4vw, 58px);
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(60, 54, 41, .08);
    }}
    header {{ padding-bottom: 28px; border-bottom: 1px solid var(--line); }}
    .eyebrow {{
      margin: 0 0 12px;
      color: var(--blue);
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    h1 {{ max-width: 920px; margin: 0; font-size: clamp(34px, 6vw, 64px); line-height: 1.1; }}
    .subtitle {{ max-width: 900px; margin: 18px 0 0; color: var(--muted); font-size: 19px; }}
    h2 {{
      margin: 58px 0 20px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--ink);
      font-size: clamp(25px, 3vw, 34px);
      line-height: 1.25;
    }}
    h3 {{ margin: 0 0 8px; font-size: 20px; }}
    p {{ margin: 9px 0; }}
    ul, ol {{ margin: 10px 0 0; padding-left: 24px; }}
    li + li {{ margin-top: 8px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 28px 0 18px;
    }}
    .metric {{
      min-height: 126px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 13px;
      background: #fff;
    }}
    .metric strong {{ display: block; color: var(--blue); font-size: 31px; line-height: 1.05; }}
    .metric span {{ display: block; margin-top: 9px; color: var(--muted); }}
    .lead {{
      padding: 20px 22px;
      border-left: 6px solid var(--blue);
      border-radius: 0 12px 12px 0;
      background: var(--blue-soft);
      font-size: 18px;
    }}
    .caveat {{
      margin-top: 16px;
      padding: 15px 18px;
      border-left: 5px solid var(--orange);
      background: var(--orange-soft);
    }}
    .two-col, .visual-grid, .fact-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .fact-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .card {{
      padding: 21px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}
    .card p:last-child {{ margin-bottom: 0; }}
    .tag {{
      display: inline-block;
      margin-bottom: 8px;
      padding: 3px 9px;
      border-radius: 999px;
      color: #fff;
      background: var(--blue);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .06em;
    }}
    figure {{
      margin: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}
    figure img {{ display: block; width: 100%; height: auto; }}
    figure img.morphology {{ aspect-ratio: 4 / 3; object-fit: cover; }}
    figcaption {{ padding: 13px 16px 16px; color: var(--muted); font-size: 14px; }}
    .chart-wrap {{
      margin: 18px 0 24px;
      padding: 14px;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}
    .summary-chart {{ display: block; width: 100%; min-width: 780px; height: auto; }}
    .svg-title {{ fill: var(--ink); font-size: 23px; font-weight: 800; }}
    .svg-note {{ fill: var(--muted); font-size: 14px; }}
    .svg-label {{ fill: var(--ink); font-size: 14px; font-weight: 700; }}
    .svg-radius {{ fill: var(--muted); font-size: 11px; }}
    .svg-value {{ fill: var(--ink); font-size: 12px; font-weight: 700; }}
    .svg-empty {{ fill: #9a9a92; font-size: 13px; font-style: italic; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; }}
    thead th {{ background: #eeeae0; }}
    tbody th {{ width: 150px; background: #faf8f2; }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    th small {{ display: block; color: var(--muted); font-weight: 500; }}
    .cell-primary {{ display: block; font-weight: 800; }}
    .cell-secondary {{ display: block; color: var(--muted); font-size: 13px; }}
    .ball-lens {{ display: block; width: 100%; height: auto; }}
    .program-flow {{ display: block; width: 100%; min-width: 900px; height: auto; }}
    .status-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 16px 0;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      font-size: 13px;
      font-weight: 750;
    }}
    .status-pill::before {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--muted);
      content: "";
    }}
    .status-pill.committed::before {{ background: var(--green); }}
    .status-pill.worktree::before {{ background: var(--orange); }}
    .status-pill.tested::before {{ background: var(--blue); }}
    .status-committed {{ color: var(--green); font-weight: 800; }}
    .status-worktree {{ color: #a74c20; font-weight: 800; }}
    .status-tested {{ color: var(--blue); font-weight: 800; }}
    .timeline {{ display: grid; gap: 12px; }}
    .timeline article {{
      display: grid;
      grid-template-columns: 112px 1fr;
      gap: 18px;
      padding: 16px 0;
      border-bottom: 1px solid var(--line);
    }}
    .timeline time {{ color: var(--blue); font-weight: 800; }}
    .timeline article:last-child {{ border-bottom: 0; }}
    .plain-source {{
      padding: 16px 18px;
      border: 1px dashed #bdb6a8;
      border-radius: 10px;
      color: var(--muted);
      background: #faf8f2;
      font-size: 13px;
    }}
    footer {{ margin-top: 52px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }}
    code {{
      padding: 2px 5px;
      border-radius: 4px;
      background: #efede6;
      font-family: Consolas, monospace;
      font-size: .92em;
    }}
    @media (max-width: 980px) {{
      .metric-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .fact-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      main {{ width: 100%; margin: 0; padding: 25px 16px 40px; border: 0; border-radius: 0; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .two-col, .visual-grid {{ grid-template-columns: 1fr; }}
      .timeline article {{ grid-template-columns: 1fr; gap: 4px; }}
    }}
    @media (max-width: 450px) {{
      .metric-grid {{ grid-template-columns: 1fr; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      main {{ width: 100%; margin: 0; padding: 0; border: 0; box-shadow: none; }}
      figure, .card, .chart-wrap, table {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">Monthly research review · 2026.07</p>
    <h1>2026 年 7 月工作总结</h1>
    <p class="subtitle">截至 2026 年 7 月 {as_of.day} 日｜微腔大扫 Q、声学灵敏度、声压信号换算与光纤球透镜模型</p>
  </header>

  <section class="metric-grid" aria-label="本月关键数字">
    <div class="metric"><strong>8</strong><span>纳入固定版图比较的 die</span></div>
    <div class="metric"><strong>{len(q_rows)}/72</strong><span>有有效 Q 的腔位</span></div>
    <div class="metric"><strong>{len(sensitivity_rows)}/72</strong><span>有灵敏度的腔位</span></div>
    <div class="metric"><strong>{best_q.max_q0_m:.3f} M</strong><span>本月最高单点 Q0</span></div>
    <div class="metric"><strong>{best_sensitivity.best_sensitivity_upa:.3f}</strong><span>最佳灵敏度，µPa/√Hz</span></div>
  </section>

  <section>
    <h2>本月结论</h2>
    <div class="lead">
      本月最完整的工作主线，是把 <code>chip_7</code> 的多 die 微腔测量推进到可横向比较的程度：
      Q/Q′、灵敏度、偏振、噪声与网分响应被统一到腔级结果和周级设计比较中。
      当前最好的 Q 和最好的灵敏度来自不同腔，支持“Q 重要，但不是灵敏度的单一决定量”这一判断。
    </div>
    <div class="fact-grid" style="margin-top:18px">
      <article class="card">
        <span class="tag">MICROCAVITY</span>
        <h3>微腔批量测量形成可比较数据集</h3>
        <p>8 个 die 的固定 72 腔位中，{len(q_rows)} 个腔位有有效 Q，{len(sensitivity_rows)} 个腔位有灵敏度；周内共保留 {sensitivity_results} 个灵敏度结果。</p>
      </article>
      <article class="card">
        <span class="tag">WORKFLOW</span>
        <h3>程序把原始采集变成标准化证据</h3>
        <p>锁模、RP 监控、大扫、模式交叉识别、TE/TM、Card、灵敏度与声压换算被串成同一条腔级 workflow；设计比较按半径 die 对与三腔 gap 组展开。</p>
      </article>
      <article class="card">
        <span class="tag">PHOTOACOUSTIC</span>
        <h3>光声显微前端进入可计算阶段</h3>
        <p>建立 532 nm 光纤球透镜的 q 参数/ABCD 模型，并用首组现场尺寸约束模型，明确下一步应补测曲率、长度和像素标定。</p>
      </article>
    </div>
    <div class="caveat">
      <strong>记录边界：</strong>本报告只使用 {args.month} 月已落盘的 campaign daily、标准化微腔结果、周报和光声显微 daily。
      可追溯日期为 {html.escape("、".join(source_days))}；其他日期不从运行日志或文件修改时间补推工作内容。
    </div>
  </section>

  <section>
    <h2>程序与 workflow 改造</h2>
    <p class="lead">
      7 月的程序工作不只是界面调整，而是把“进入一个腔目录—采集—识别模式—锁模—声学测量—Card 留存”
      连成闭环。修改目标是减少重复选择、避免旧数据被覆盖，并让 Q、偏振、灵敏度、形貌和人工备注回到同一个腔对象。
    </p>
    <div class="status-row" aria-label="程序改动状态">
      <span class="status-pill committed">本地 checkpoint：2026-07-22</span>
      <span class="status-pill worktree">后续改动：仍在当前工作树</span>
      <span class="status-pill tested">本次复核：132 项聚焦测试通过</span>
    </div>

    <div class="chart-wrap">
      {program_flow_svg()}
    </div>

    <div class="fact-grid">
      <article class="card">
        <span class="tag">LOCK + MONITOR</span>
        <h3>锁模、仪器租约与 RP 浮窗</h3>
        <p>建立常驻 TOPTICA TCP 服务，使控制器只在首次连接时提示；目标跳转保持扫频，不再额外执行 safe-off。锁模流程加入 PID 预载回读、直接 I=-100、2 s 稳定性观察和异常恢复租约。</p>
        <p>RP 浮窗把示波器功率、频谱 PSD 与网分响应放进同一监控界面，并保留分栏位置、颜色、过期状态和饱和告警。</p>
      </article>
      <article class="card">
        <span class="tag">LARGE SCAN</span>
        <h3>大扫采集、门控与旧数据保护</h3>
        <p>大扫采样率固定为 200 kSa/s，并补齐扫频开始确认、触发窗口、采集门控和待机恢复。对同一目录再次采集前，旧数据按原创建日期归档并写入清单，避免直接覆盖。</p>
        <p>识别阈值统一表述为透过率 ≤0.9（即凹陷深度 ≥0.1），分析后可继续刷新腔 Card。</p>
      </article>
      <article class="card">
        <span class="tag">MODE FAMILY</span>
        <h3>模式交叉与 TE/TM 整理</h3>
        <p>色散识别从局部逐点匹配改为全局平滑跟踪：允许短暂缺点，以斜率和曲率连续性约束家族，并比较独立交叉、避交叉和非参数平滑模型，降低交叉处换线和误删真实弯曲的概率。</p>
        <p>Q/Q′ 可按主家族 FSR 顺序或人工映射识别为 TE/TM，并把标签、置信度和过期状态回填到腔级结果。</p>
      </article>
      <article class="card">
        <span class="tag">ACOUSTICS</span>
        <h3>灵敏度绘图与声压换算</h3>
        <p>噪声、网分响应和灵敏度图按实测频段绘制并平滑；响应可标 3 dB、灵敏度可标 10 dB 交点和最佳灵敏度点，也可在“全部原始范围”和“声压标定共同范围”间切换。</p>
        <p>新增标定信号采集和信号响应换算：在共同频率范围内结合网分 raw、声压标定及锁模光功率比例，输出 Pa/√Hz、Pa RMS/RBW、dB SPL 与频带积分声压。</p>
      </article>
      <article class="card">
        <span class="tag">CARD + LABEL</span>
        <h3>Card、偏振视图与人工挑选</h3>
        <p>Card 同时整理 TE/TM（及其来源 Q/Q′）的 Q、深度、灵敏度和形貌图；目标锁模页可直接切换偏振、查看相应 Q 表，并按 Q 与深度推荐潜在高灵敏度模式。</p>
        <p>新增腔标签：普通/绿色为默认，优秀/黄色、值得关注/红色可选，并可添加备注；标签同步进入单腔 Card、die 总结和多腔对比工具。</p>
      </article>
      <article class="card">
        <span class="tag">PANEL + COUPLING</span>
        <h3>目录记忆、功率保存与自动耦合</h3>
        <p>从某个 die/cavity 进入测量后，后续 Q、大扫、灵敏度、信号和标签路径都跟随该腔，直到进入另一腔；大扫前自动保存监测功率和输出功率，面板也记住偏振、目标来源和手动波长等状态。</p>
        <p>自动耦合解析已兼容 <code>CH1/in1</code> 功率文本，并为六轴回中加入自适应步进、回读容差与面板按钮。</p>
      </article>
    </div>

    <h3 style="margin-top:30px">实现状态与实验价值</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>模块</th><th>本月修改</th><th>当前状态</th><th>对测量的直接价值</th></tr>
        </thead>
        <tbody>
          <tr>
            <th>锁模与 RP 监控</th>
            <td>常驻激光服务、PID/恢复流程、仪器租约、功率/PSD/网分浮窗</td>
            <td><span class="status-committed">已进入本地 checkpoint</span></td>
            <td>减少重复连接和控制冲突，保留锁模现场证据</td>
          </tr>
          <tr>
            <th>大扫与家族识别</th>
            <td>200 kSa/s、采集门控、旧数据归档、交叉模式全局平滑跟踪</td>
            <td><span class="status-worktree">后续工作树改动</span></td>
            <td>降低覆盖、错配家族和边界异常对 Q/色散结论的影响</td>
          </tr>
          <tr>
            <th>TE/TM、Card 与标签</th>
            <td>偏振识别、双偏振结果、形貌 figure 索引、颜色等级和备注</td>
            <td><span class="status-worktree">后续工作树改动</span></td>
            <td>让一个腔的自动结果和人工判断可以一起筛选、复盘</td>
          </tr>
          <tr>
            <th>灵敏度与声压信号</th>
            <td>动态频轴、平滑、带宽交点、光功率修正和声压换算</td>
            <td><span class="status-committed">基础链路已 checkpoint</span>；绘图仍有后续修改</td>
            <td>从“看谱”推进到可比较灵敏度和可追溯声压结果</td>
          </tr>
          <tr>
            <th>面板与自动耦合</th>
            <td>腔目录/功率/选项记忆，自动耦合功率解析与六轴回中</td>
            <td><span class="status-worktree">后续工作树改动</span></td>
            <td>减少重复输入及因目录、通道文本变化造成的现场中断</td>
          </tr>
          <tr>
            <th>离线验证</th>
            <td>锁模、RP、采集归档、交叉识别、偏振、Card、绘图、耦合与记忆</td>
            <td><span class="status-tested">16 个模块、132 项测试通过</span></td>
            <td>覆盖主要回归风险；仍不能替代仪器联机复测</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="caveat">
      <strong>版本边界：</strong>2026-07-22 的本地 checkpoint
      <code>04ff067</code> 涵盖 29 个文件（+18,719 / −1,182），主要是锁模、RP 监控、仪器租约和声压换算基础链路。
      checkpoint 之后，当前工作树还有 18 个 tracked 文件的后续修改（+3,657 / −242）以及新增模块/测试，
      包括大扫、交叉家族、TE/TM、Card/标签、路径记忆和自动耦合；这些不写成已发布版本。
      当前测试目录共 30 个文件、214 个测试函数，本次实际运行的是其中 16 个相关模块、132 项测试，全部通过；
      离线测试不替代激光器、RP、位移台和网分的联机确认。
    </div>
  </section>

  <section>
    <h2>微腔测量：结果与规律</h2>
    <div class="two-col">
      <article class="card">
        <h3>最高 Q0</h3>
        <p><strong>{best_q.die} / cavity_{best_q.cavity}</strong>：{best_q.max_q0_m:.3f} M，
        当前显示偏振为 {html.escape(best_q.q_polarization or "未标")}；日记记录峰值位于
        1531.979529 nm，靠近 1530–1570 nm 扫描短波边界，锁模候选仍需复核边界拟合稳定性。</p>
      </article>
      <article class="card">
        <h3>最好灵敏度</h3>
        <p><strong>{best_sensitivity.die} / cavity_{best_sensitivity.cavity}</strong>：
        {best_sensitivity.best_sensitivity_upa:.3f} µPa/√Hz @ 560.960 kHz，
        灵敏度结果偏振为 {html.escape(best_sensitivity.sensitivity_polarization or "未标")}；
        对应锁定模式为 mode2、μ=9、1534.262661 nm、Q0=1.329 M。</p>
      </article>
    </div>

    <div class="chart-wrap">
      {bar_chart_svg(rows)}
    </div>
    <p class="plain-source">图中使用每个 die 的中位数，避免单个极高 Q 或单个灵敏度尖点主导判断。灵敏度数值越低越好；<code>die_2_1</code> 本月无正式结果，因此保留为空。</p>

    <h3 style="margin-top:30px">三腔 gap 组的稳健比较</h3>
    <p>每个 die 固定把 c1–c3、c4–c6、c7–c9 作为三组；空腔保留，但不以零值参与统计。表内第一行是组中位 Q0（M），第二行是组中位灵敏度。</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>die / 半径</th><th>组 1 · c1–c3</th><th>组 2 · c4–c6</th><th>组 3 · c7–c9</th></tr></thead>
        <tbody>{gap_table(rows)}</tbody>
      </table>
    </div>

    <div class="two-col" style="margin-top:20px">
      <article class="card">
        <h3>较明确的正向组</h3>
        <ul>
          <li>125 µm 的 <code>die_1_1</code> 组 3：组中位灵敏度约 1.82 µPa/√Hz；Q 不是三组最高，但噪声底明显更低。</li>
          <li>65 µm 的 <code>die_2_3</code> 组 3：组中位灵敏度约 2.30 µPa/√Hz，兼具较低噪声和较高响应。</li>
          <li>105 µm 的 <code>die_1_4</code> 组 2：由 cavity_5 的高响应与 1.96 µPa/√Hz 最佳值拉动。</li>
        </ul>
      </article>
      <article class="card">
        <h3>不能过度解释的部分</h3>
        <ul>
          <li><code>die_2_1</code> 缺测，85 µm 半径没有成对对照。</li>
          <li>热噪声目前仍是锁模测量链路的总噪声代理，尚未用关光/未锁背景分离纯热机械噪声。</li>
          <li>具体 gap 数值在两套设计资料中不一致，因此本月只使用组 1/2/3，不写未经确认的数值 gap。</li>
        </ul>
      </article>
    </div>
  </section>

  <section>
    <h2>代表图：Q、灵敏度与腔形貌</h2>
    <div class="visual-grid">
      <figure>
        <img src="{q_uri}" alt="{best_q.die} cavity {best_q.cavity} 的大扫 Q0、Q1 与透过深度随波长变化">
        <figcaption>本月最高单点 Q0 所在腔的标准化 Q 趋势。两条模式家族在 1530–1570 nm 内有不同的 Q 和耦合深度演化。</figcaption>
      </figure>
      <figure>
        <img src="{sensitivity_uri}" alt="{best_sensitivity.die} cavity {best_sensitivity.cavity} 的噪声、声学响应与灵敏度谱">
        <figcaption>本月最佳灵敏度：1.353 µPa/√Hz @ 560.960 kHz。图中同步给出噪声 PSD、平滑网分响应和灵敏度谱。</figcaption>
      </figure>
      <figure>
        <img class="morphology" src="{morphology_uri}" alt="die 1-4 cavity 5 的显微形貌">
        <figcaption><code>die_1_4 / cavity_5</code> 腔形貌。该腔得到 1.961 µPa/√Hz 的本月次优代表结果，说明显微形貌、耦合、偏振和声学响应应一起留存。</figcaption>
      </figure>
      <article class="card">
        <h3>偏振与模式选择</h3>
        <p>当前周级展示中，有效 Q 腔位按偏振分为 TE {q_pol_count["TE"]} 个、TM {q_pol_count["TM"]} 个；灵敏度腔位分为 TE {s_pol_count["TE"]} 个、TM {s_pol_count["TM"]} 个。</p>
        <p>最好的灵敏度来自 TM 结果，但不同半径与 gap 组的 TE/TM 分布不均衡，暂不能把整体差异直接归因于偏振。</p>
        <p>本月数据还显示：最高 Q 腔并非最佳灵敏度腔。后续推荐模式应同时看 Q、耦合深度、噪声、响应峰值、锁定光功率与稳定性。</p>
      </article>
    </div>
  </section>

  <section>
    <h2>声压信号换算：已跑通，但仍是探索结果</h2>
    <div class="two-col">
      <article class="card">
        <h3>已完成的换算</h3>
        <p><code>die_1_1 / cavity_9 / Q′</code> 使用既有网分响应 raw 文件与声压标定数据，把 RP 频谱仪信号换算为声压。</p>
        <p>约 12.994 kHz 处得到 5.995×10⁻³ Pa RMS/RBW、49.54 dB SPL；频段积分为 2.047×10⁻³ Pa RMS、40.20 dB SPL，RBW=823.43 Hz。</p>
      </article>
      <article class="card">
        <h3>结论边界</h3>
        <p>该结果未做背景扣除，单 RBW 峰值和积分值都包含噪声，因此只能说明“从频谱到声压”的计算链路已贯通，不能视为已确认的窄带声源强度。</p>
        <p>下一步应在峰附近缩窄频段，并补采同设置背景谱做差分。</p>
      </article>
    </div>
  </section>

  <section>
    <h2>光声显微准备：光纤球透镜模型</h2>
    <figure>
      {ball_lens_svg()}
      <figcaption>单模光纤 → 无芯石英扩束段 → 熔融球形端面 → 空气。主要折射发生在最后的石英—空气球面；结构示意不按比例。</figcaption>
    </figure>
    <div class="two-col" style="margin-top:18px">
      <article class="card">
        <h3>现场事实</h3>
        <ul>
          <li>波长 532 nm，球头外形直径约 280 µm。</li>
          <li>赤道面到焦点约 720 µm；按 R=140 µm 换算，顶点工作距离约 580 µm。</li>
          <li>D4σ 焦点直径约 10 µm，但长轴/短轴定义、像素—物面换算和不确定度尚未补齐。</li>
        </ul>
      </article>
      <article class="card">
        <h3>模型判断</h3>
        <ul>
          <li>用 q 参数和 ABCD 矩阵分开计算无芯段扩束、球面折射、工作距离和焦斑。</li>
          <li>只调整无芯段长度 Lᵥ 不能同时解释 580 µm 工作距离与 10 µm 焦斑。</li>
          <li>优先核对真实曲率、Lᵥ、M²、球差、位置零点与像素标定，不直接判定实测无效。</li>
        </ul>
      </article>
    </div>
  </section>

  <section>
    <h2>本月工作时间线</h2>
    <div class="timeline">
      <article><time>7 月 13 日</time><div><strong>建立统一灵敏度结果。</strong> <code>die_1_1 / cavity_1</code> 得到 1.688 µPa/√Hz，作为后续批量流程的首组结果。</div></article>
      <article><time>7 月 14 日</time><div><strong>完成 die_1_1 主体测量。</strong> cavity_2–cavity_9 完成 16 组 Q/Q′，并完成 8 个灵敏度结果；同时首次跑通声压信号换算。</div></article>
      <article><time>7 月 15 日</time><div><strong>无正式结果落盘。</strong> 不从调试日志推断完成内容。</div></article>
      <article><time>7 月 16 日</time><div><strong>推进 die_1_2 与 die_2_2。</strong> 共 19 组大扫 Q、16 个灵敏度结果；其中一组采集有效但未形成可用模式家族。</div></article>
      <article><time>7 月 17 日</time><div><strong>本月测量量最大。</strong> die_1_3、die_1_4、die_2_3 共 40 组大扫 Q、26 个灵敏度结果，覆盖 25 个腔。</div></article>
      <article><time>7 月 18 日</time><div><strong>完成 die_2_4。</strong> 8 个腔各保留一组大扫 Q 与一个灵敏度结果。</div></article>
      <article><time>7 月 19 日</time><div><strong>无正式结果落盘。</strong> 保留为空，不把分析或调试推测成测量完成。</div></article>
      <article><time>7 月 23 日</time><div><strong>建立光纤球透镜模型。</strong> 完成 q 参数/ABCD 计算和自包含模型页面，并用首组现场 WD 与 D4σ 数据检查模型一致性。</div></article>
    </div>
  </section>

  <section>
    <h2>下月优先级</h2>
    <ol>
      <li>补测 <code>die_2_1</code>，完成 85 µm 半径 pair；确认两套设计资料中的具体 gap 数值。</li>
      <li>对 <code>die_1_1</code> 组 3、<code>die_1_4/cavity_5</code>、<code>die_2_3</code> 组 3 各做至少 3 次重复，并同步记录锁模光功率。</li>
      <li>复核色散不确定组与扫描边界高 Q 点，继续区分“Q 拟合成功”和“模式家族/色散模型可靠”。</li>
      <li>增加关光、未锁或电子背景谱，分离总噪声代理中的背景成分。</li>
      <li>光纤球透镜补测真实 R、Lᵥ、轴向光斑序列和 µm/pixel，再决定下一轮加工长度扫描。</li>
    </ol>
  </section>

  <footer>
    <div>生成日期：{args.as_of}｜统计范围：{args.month}-01 至 {args.as_of}</div>
    <div>事实来源：Batch_260515 的 7 月 daily、chip_7 标准化结果、2026-07-13 至 2026-07-19 周报、photoacoustic_microscopy 的 2026-07-23 daily，以及本地 Git checkpoint、当前工作树差异和本次聚焦测试结果。全部图片与图表已内嵌；页面不包含外部或本地文件链接。</div>
  </footer>
</main>
</body>
</html>
"""


def validate_self_contained(report: str) -> None:
    if re.search(r"<a\b", report, flags=re.IGNORECASE):
        raise RuntimeError("Report contains a hyperlink")
    image_sources = re.findall(
        r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']",
        report,
        flags=re.IGNORECASE,
    )
    if not image_sources:
        raise RuntimeError("Report contains no raster images")
    bad_sources = [source for source in image_sources if not source.startswith("data:image/")]
    if bad_sources:
        raise RuntimeError(f"Report contains non-embedded image sources: {bad_sources}")
    if "<svg" not in report:
        raise RuntimeError("Report contains no inline SVG")


def main() -> int:
    args = parse_args()
    if args.output.exists() and not args.force:
        raise FileExistsError(
            f"Refusing to overwrite existing report without --force: {args.output}"
        )
    report = generate_report(args)
    validate_self_contained(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output.resolve()),
                "bytes": args.output.stat().st_size,
                "embedded_raster_images": len(
                    re.findall(r"<img\b", report, flags=re.IGNORECASE)
                ),
                "inline_svgs": len(
                    re.findall(r"<svg\b", report, flags=re.IGNORECASE)
                ),
                "hyperlinks": len(
                    re.findall(r"<a\b", report, flags=re.IGNORECASE)
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
