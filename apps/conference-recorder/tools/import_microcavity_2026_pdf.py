#!/usr/bin/env python3
"""Import a supported Microcavity 2026 handbook into a mobile conference JSON.

The importer recognizes both the 54-page first edition and the 58-page complete
edition. It reads the digitally generated PDF, uses table geometry and character
coordinates, and writes one deterministic JSON document. Real conference data
stays outside Git because generated conference JSON files are ignored.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import pdfplumber


EDITION_PROFILES: dict[int, dict[str, Any]] = {
    54: {
        "edition": "first-edition",
        "editionLabel": "会议手册第一版",
        "schedulePages": range(13, 20),
        "posterPages": range(43, 54),
        "expectedTalks": 40,
        "expectedPosters": 131,
        "expectedUpdateTitles": 3,
        "location": "会场地点待手册核验",
        "venue": "会场待确认",
        "posterVenue": "会场待确认",
        "openingStart": "14:00",
        "openingEnd": "14:30",
        "openingChair": "待定",
        "includeWorkshops": True,
        "roundtableEnd": "17:30",
        "warnings": [
            "3 场报告题目在手册第一版中为“更新中”。",
            "圆桌论坛总体日程写至 17:00，详细日程写至 17:30；App 暂采用详细日程。",
        ],
    },
    58: {
        "edition": "complete",
        "editionLabel": "会议手册完整版",
        "schedulePages": range(13, 20),
        "posterPages": range(47, 58),
        "expectedTalks": 39,
        "expectedPosters": 137,
        "expectedUpdateTitles": 0,
        "location": "成都空港国际会议中心一楼多功能厅",
        "venue": "成都空港国际会议中心一楼多功能厅",
        "posterVenue": "成都空港国际会议中心一楼多功能厅序厅",
        "openingStart": "14:30",
        "openingEnd": "15:00",
        "openingChair": "许秀来",
        "includeWorkshops": False,
        "roundtableEnd": "17:00",
        "warnings": [],
    },
}

INSTITUTION_RE = re.compile(
    r"大学|学院|研究所|研究院|技术院|实验室|中心|国家实验室|"
    r"University|Institute|Academy|Laboratory|School|College|Center|Hospital|"
    r"Technology|Photonics|CNRS|EPFL|ETH",
    re.IGNORECASE,
)
CJK_ONLY_RE = re.compile(r"^[\u3400-\u9fff]+$")
POSTER_CODE_RE = re.compile(r"Microcavity2026-\d+(?:-\d+)+")
TIME_RE = re.compile(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})")
PLENARY_IDS_BY_SPEAKER = {
    "孙志培": "plenary-1",
    "王兴军": "plenary-2",
    "宋清海": "plenary-3",
    "饶云江": "plenary-4",
}


class ImportValidationError(RuntimeError):
    """Raised when the PDF or generated output violates an expected invariant."""


def normalize_text(value: str) -> str:
    value = html.unescape(value.replace("\t", " "))
    value = (
        value.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )
    return re.sub(r"\s+", " ", value).strip()


def normalize_chinese_name_spacing(value: str) -> str:
    value = normalize_text(value)
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)


def chars_text(chars: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(chars, key=lambda char: char["x0"])
    return normalize_text("".join(char["text"] for char in ordered))


def group_words_by_line(words: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    tops: list[float] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not groups or abs(word["top"] - tops[-1]) > 2:
            groups.append([word])
            tops.append(word["top"])
        else:
            groups[-1].append(word)
    return [sorted(group, key=lambda item: item["x0"]) for group in groups]


def group_chars_by_line(chars: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for char in sorted(chars, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(char["top"] - lines[-1]["top"]) > 0.8:
            lines.append({"top": char["top"], "chars": [char]})
        else:
            lines[-1]["chars"].append(char)
    for line in lines:
        line["text"] = chars_text(line["chars"])
    return [line for line in lines if line["text"]]


def join_wrapped_lines(parts: Iterable[str]) -> str:
    output = ""
    for part in parts:
        part = normalize_text(part)
        if not part:
            continue
        if not output:
            output = part
        elif output.endswith("-"):
            output += part
        elif re.search(r"[\u3400-\u9fff]$", output) and re.match(
            r"^[\u3400-\u9fff]", part
        ):
            output += part
        else:
            output += " " + part
    return normalize_text(output)


def normalize_time(value: str) -> str:
    hour, minute = value.split(":", 1)
    return f"{int(hour):02d}:{minute}"


def time_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def join_person_tokens(tokens: list[str]) -> str:
    if tokens and all(CJK_ONLY_RE.match(token) for token in tokens):
        return "".join(tokens)
    return normalize_text(" ".join(tokens))


def split_speaker_affiliation(tokens: list[str]) -> tuple[str, str]:
    affiliation_start = next(
        (index for index, token in enumerate(tokens) if INSTITUTION_RE.search(token)),
        None,
    )
    if affiliation_start is None:
        return join_person_tokens(tokens), ""
    return (
        join_person_tokens(tokens[:affiliation_start]),
        join_person_tokens(tokens[affiliation_start:]),
    )


def parse_session_metadata(page_text: str) -> tuple[dict[str, Any] | None, str]:
    topic = None
    for line in page_text.splitlines():
        match = re.search(
            r"专题\s*(\d+)\s*[：:]\s*(.*?)\s+2026/08/(\d+)", line
        )
        if match:
            topic = {
                "number": int(match.group(1)),
                "title": normalize_text(match.group(2)),
                "date": f"2026-08-{int(match.group(3)):02d}",
            }
            break

    chair = ""
    chair_match = re.search(r"主持人\s*[：:]\s*([^\n]+)", page_text)
    if chair_match:
        chair = normalize_chinese_name_spacing(chair_match.group(1))
    return topic, chair


def extract_schedule(
    pdf: pdfplumber.PDF, schedule_pages: Iterable[int]
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    talks: list[dict[str, Any]] = []
    sessions: dict[int, dict[str, Any]] = {}

    for page_number in schedule_pages:
        page = pdf.pages[page_number - 1]
        page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
        topic, chair = parse_session_metadata(page_text)
        if topic:
            sessions[topic["number"]] = {
                **topic,
                "chair": chair,
                "sourcePage": page_number,
            }

        words = page.extract_words(
            extra_attrs=["fontname", "size"], x_tolerance=1, y_tolerance=1
        )
        tables = page.find_tables()
        if len(tables) != 1:
            raise ImportValidationError(
                f"PDF page {page_number}: expected one schedule table, found {len(tables)}"
            )

        for row in tables[0].rows:
            cells = sorted((cell for cell in row.cells if cell), key=lambda cell: cell[0])
            if len(cells) < 2:
                continue
            left_cell, right_cell = cells[0], cells[-1]
            row_top, row_bottom = left_cell[1], left_cell[3]
            left_words = [
                word
                for word in words
                if row_top < word["top"] < row_bottom + 4
                and left_cell[0] <= word["x0"] < left_cell[2]
            ]
            left_text = normalize_text(
                "".join(
                    word["text"]
                    for word in sorted(left_words, key=lambda item: (item["top"], item["x0"]))
                )
            )
            time_match = TIME_RE.search(left_text)
            if not time_match:
                continue

            right_words = [
                word
                for word in words
                if row_top < word["top"] < row_bottom + 8
                and right_cell[0] <= word["x0"] < right_cell[2] + 2
            ]
            row_text = normalize_text(" ".join(word["text"] for word in right_words))
            if not (
                "大会报告" in row_text
                or "邀请报告" in row_text
                or re.search(r"\bOral\s+\d+-\d+", row_text)
            ):
                continue

            bold_words = [word for word in right_words if "Bold" in word["fontname"]]
            title = join_wrapped_lines(
                normalize_text(" ".join(word["text"] for word in line))
                for line in group_words_by_line(bold_words)
            )

            oral_match = re.match(r"Oral\s+(\d+)-(\d+)\s*(.*)", title)
            if oral_match:
                session_number = int(oral_match.group(1))
                ordinal = 4 + int(oral_match.group(2))
                badge = f"Oral {oral_match.group(1)}-{oral_match.group(2)}"
                title = oral_match.group(3).strip()
            elif "大会报告" in row_text:
                session_number = 0
                ordinal = 1 + sum(talk["sessionNumber"] == 0 for talk in talks)
                badge = "大会报告"
            else:
                if not topic:
                    raise ImportValidationError(
                        f"PDF page {page_number}: invited talk has no topic header"
                    )
                session_number = topic["number"]
                ordinal = 1 + sum(
                    talk["sessionNumber"] == session_number
                    and talk["badge"] == "邀请报告"
                    for talk in talks
                )
                badge = "邀请报告"

            regular_words = [
                word for word in right_words if "Bold" not in word["fontname"]
            ]
            person_lines: list[list[str]] = []
            for line in group_words_by_line(regular_words):
                tokens = [word["text"] for word in line]
                text = normalize_text(" ".join(tokens))
                if text not in ("大会报告", "邀请报告"):
                    person_lines.append(tokens)
            person_tokens = person_lines[-1] if person_lines else []
            speaker, affiliation = split_speaker_affiliation(person_tokens)

            if session_number == 0:
                item_id = f"plenary-{ordinal}"
            elif session_number == 2 and ordinal == 6:
                item_id = "talk-hzg"
            else:
                item_id = f"talk-{session_number}-{ordinal}"
            if session_number == 0:
                item_id = PLENARY_IDS_BY_SPEAKER.get(speaker, item_id)

            talks.append(
                {
                    "id": item_id,
                    "kind": "talk",
                    "title": title,
                    "speaker": speaker,
                    "affiliation": affiliation,
                    "start": normalize_time(time_match.group(1)),
                    "end": normalize_time(time_match.group(2)),
                    "badge": badge,
                    "sessionNumber": session_number,
                    "sourcePage": page_number,
                    "sourcePrintedPage": page_number - 4,
                }
            )

    return talks, sessions


def line_with_small_markers(
    line: dict[str, Any], row_chars: list[dict[str, Any]]
) -> str:
    elements: list[tuple[float, int, str]] = [
        (char["x0"], 0, char["text"]) for char in line["chars"]
    ]
    for char in row_chars:
        if char["size"] < 8 and abs(char["bottom"] - line["top"]) < 1.6:
            marker = "," if char["text"] in ";；" else char["text"]
            elements.append((char["x0"], 1, marker))
    return normalize_text(
        "".join(text for _, _, text in sorted(elements, key=lambda item: (item[0], item[1])))
    )


def parse_affiliations(text: str) -> tuple[list[dict[str, Any]], bool]:
    normalized = text.replace("；", ";")
    numbered = [
        {"id": int(match.group(1)), "name": normalize_text(match.group(2))}
        for match in re.finditer(
            r"(\d+)\.\s*(.*?)(?=;\s*\d+\.|$)", normalized
        )
    ]
    if numbered and re.match(r"^\d+\.", normalized):
        return numbered, True
    return [{"id": 1, "name": normalize_text(text)}], False


def parse_authors(
    author_stream: str, affiliations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    valid_ids = {affiliation["id"] for affiliation in affiliations}
    authors: list[dict[str, Any]] = []
    for raw_token in re.split(r"[;；]", author_stream):
        token = normalize_text(raw_token)
        if not token:
            continue
        corresponding = "*" in token
        token = token.replace("*", "").strip()
        refs: list[int] = []
        mapping_status = "explicit"

        suffix = re.search(r"(\d+(?:,\d+)*)$", token)
        if suffix:
            candidates = [int(value) for value in suffix.group(1).split(",")]
            if not set(candidates) <= valid_ids:
                raise ImportValidationError(
                    f"Unknown affiliation reference {candidates} for author {token}"
                )
            refs = candidates
            token = token[: suffix.start()].strip()

        if not refs and len(valid_ids) == 1:
            refs = [next(iter(valid_ids))]
            mapping_status = "inferred_single_affiliation"
        elif not refs:
            mapping_status = "unresolved"

        authors.append(
            {
                "name": token,
                "affiliationIds": refs,
                "corresponding": corresponding,
                "mappingStatus": mapping_status,
            }
        )
    return authors


def extract_posters(
    pdf: pdfplumber.PDF, poster_pages: Iterable[int]
) -> list[dict[str, Any]]:
    posters: list[dict[str, Any]] = []

    for page_number in poster_pages:
        page = pdf.pages[page_number - 1]
        tables = page.find_tables()
        if len(tables) != 1:
            raise ImportValidationError(
                f"PDF page {page_number}: expected one poster table, found {len(tables)}"
            )

        for row in tables[0].rows:
            cells = sorted((cell for cell in row.cells if cell), key=lambda cell: cell[0])
            if len(cells) < 2:
                continue
            left_cell, right_cell = cells[0], cells[-1]
            row_top, row_bottom = left_cell[1], left_cell[3]
            left_text = chars_text(
                char
                for char in page.chars
                if row_top < char["top"] < row_bottom + 3
                and left_cell[0] < char["x0"] < left_cell[2]
            )
            code_match = POSTER_CODE_RE.search(left_text)
            if not code_match:
                continue
            code = code_match.group(0)

            row_chars = [
                char
                for char in page.chars
                if row_top < char["top"] < row_bottom + 8
                and right_cell[0] <= char["x0"] < right_cell[2] + 2
            ]
            main_lines = group_chars_by_line(
                char for char in row_chars if char["size"] >= 8
            )
            if len(main_lines) < 3:
                raise ImportValidationError(
                    f"{code}: expected title, authors, and affiliation lines"
                )

            numbered_starts = [
                index
                for index, line in enumerate(main_lines[1:], 1)
                if re.match(r"^\d+\.", line["text"])
            ]
            if numbered_starts:
                affiliation_start = numbered_starts[0]
            else:
                affiliation_start = len(main_lines) - 1
                while affiliation_start > 1 and INSTITUTION_RE.search(
                    main_lines[affiliation_start - 1]["text"]
                ):
                    affiliation_start -= 1

            author_start = affiliation_start - 1
            while author_start > 0 and (
                ";" in main_lines[author_start - 1]["text"]
                or "；" in main_lines[author_start - 1]["text"]
            ):
                author_start -= 1
            if author_start < 1:
                raise ImportValidationError(f"{code}: could not separate title and authors")

            title = join_wrapped_lines(
                line["text"] for line in main_lines[:author_start]
            )
            author_stream = "".join(
                line_with_small_markers(line, row_chars)
                for line in main_lines[author_start:affiliation_start]
            )
            affiliation_text = join_wrapped_lines(
                line["text"] for line in main_lines[affiliation_start:]
            )
            affiliations, _ = parse_affiliations(affiliation_text)
            authors = parse_authors(author_stream, affiliations)

            suffix = code.removeprefix("Microcavity2026-").lower()
            poster_id = "poster-hzg" if code == "Microcavity2026-0630-3" else f"poster-{suffix}"
            speaker = "；".join(
                author["name"] + ("*" if author["corresponding"] else "")
                for author in authors
            )
            if len(affiliations) == 1:
                affiliation_display = affiliations[0]["name"]
            else:
                affiliation_display = "；".join(
                    f"{affiliation['id']}. {affiliation['name']}"
                    for affiliation in affiliations
                )

            posters.append(
                {
                    "id": poster_id,
                    "kind": "poster",
                    "code": code,
                    "title": title,
                    "speaker": speaker,
                    "affiliation": affiliation_display,
                    "badge": "海报",
                    "authors": authors,
                    "affiliations": affiliations,
                    "sourcePage": page_number,
                    "sourcePrintedPage": page_number - 4,
                }
            )

    return posters


def session_items(talks: list[dict[str, Any]], session_number: int) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in talk.items() if key != "sessionNumber"}
        for talk in talks
        if talk["sessionNumber"] == session_number
    ]


def build_session(
    talks: list[dict[str, Any]],
    metadata: dict[str, Any],
    session_number: int,
    profile: dict[str, Any],
) -> dict[str, Any]:
    items = session_items(talks, session_number)
    update_count = sum(item["title"] == "更新中" for item in items)
    note = f"4 场邀请报告 + 2 场 Oral；直接提取自{profile['editionLabel']}。"
    if update_count:
        note += f"其中 {update_count} 场题目在手册原文中为“更新中”。"
    return {
        "id": f"session-{session_number}",
        "title": f"专题 {session_number}：{metadata['title']}",
        "start": items[0]["start"],
        "end": items[-1]["end"],
        "venue": profile["venue"],
        "chair": metadata["chair"],
        "note": note,
        "sourcePage": metadata["sourcePage"],
        "items": items,
    }


def build_payload(
    pdf_path: Path,
    talks: list[dict[str, Any]],
    session_metadata: dict[int, dict[str, Any]],
    posters: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    plenary_items = session_items(talks, 0)
    update_count = sum(item["title"] == "更新中" for item in plenary_items)
    opening_note = (
        f"主持人：{profile['openingChair']}；直接提取自{profile['editionLabel']}。"
        if profile["openingChair"] != "待定"
        else f"主持人信息在{profile['editionLabel']}中为待定。"
    )
    plenary_note = f"{len(plenary_items)} 场大会报告；直接提取自{profile['editionLabel']}。"
    if update_count:
        plenary_note += f"其中 {update_count} 场题目在手册原文中为“更新中”。"
    day_one_sessions = [
        {
            "id": "opening",
            "title": "开幕式",
            "start": profile["openingStart"],
            "end": profile["openingEnd"],
            "venue": profile["venue"],
            "chair": profile["openingChair"],
            "note": opening_note,
            "sourcePage": 13,
            "items": [
                {
                    "id": "opening-1",
                    "kind": "ceremony",
                    "title": "开幕式",
                    "speaker": profile["openingChair"],
                    "affiliation": "",
                    "start": profile["openingStart"],
                    "end": profile["openingEnd"],
                    "badge": "会议环节",
                    "sourcePage": 13,
                }
            ],
        },
        {
            "id": "plenary",
            "title": "大会报告",
            "start": plenary_items[0]["start"],
            "end": plenary_items[-1]["end"],
            "venue": profile["venue"],
            "chair": "",
            "note": plenary_note,
            "sourcePage": 13,
            "items": plenary_items,
        },
    ]
    if profile["includeWorkshops"]:
        day_one_sessions.append(
            {
                "id": "workshops",
                "title": "Workshops",
                "start": "19:00",
                "end": "21:00",
                "venue": profile["venue"],
                "chair": "",
                "note": "手册第一版未列出工作坊细分议题。",
                "sourcePage": 13,
                "items": [
                    {
                        "id": "workshop-1",
                        "kind": "workshop",
                        "title": "Workshops",
                        "speaker": "",
                        "affiliation": "",
                        "start": "19:00",
                        "end": "21:00",
                        "badge": "工作坊",
                        "sourcePage": 13,
                    }
                ],
            }
        )
    days = [
        {
            "id": "2026-08-10",
            "label": "8月10日",
            "weekday": "周一",
            "sessions": day_one_sessions,
        },
        {
            "id": "2026-08-11",
            "label": "8月11日",
            "weekday": "周二",
            "sessions": [
                build_session(talks, session_metadata[1], 1, profile),
                build_session(talks, session_metadata[2], 2, profile),
                build_session(talks, session_metadata[3], 3, profile),
                {
                    "id": "poster-session",
                    "title": "张贴报告",
                    "start": "16:10",
                    "end": "17:30",
                    "venue": profile["posterVenue"],
                    "chair": "",
                    "note": f"完整名录共 {len(posters)} 条，可从会议页进入海报检索。",
                    "sourcePage": 16,
                    "items": [
                        {
                            "id": "poster-session-1",
                            "kind": "poster-session",
                            "title": "张贴报告",
                            "speaker": f"{len(posters)} 张海报名录",
                            "affiliation": "",
                            "start": "16:10",
                            "end": "17:30",
                            "badge": "海报环节",
                            "sourcePage": 16,
                        }
                    ],
                },
            ],
        },
        {
            "id": "2026-08-12",
            "label": "8月12日",
            "weekday": "周三",
            "sessions": [
                build_session(talks, session_metadata[4], 4, profile),
                build_session(talks, session_metadata[5], 5, profile),
                build_session(talks, session_metadata[6], 6, profile),
                {
                    "id": "roundtable",
                    "title": "圆桌论坛",
                    "start": "16:10",
                    "end": profile["roundtableEnd"],
                    "venue": profile["venue"],
                    "chair": "",
                    "note": (
                        "详细日程写至 17:30；总体日程表写至 17:00，结束时间需现场核验。"
                        if profile["edition"] == "first-edition"
                        else "总体日程与详细日程均写至 17:00。"
                    ),
                    "sourcePage": 19,
                    "items": [
                        {
                            "id": "roundtable-1",
                            "kind": "roundtable",
                            "title": "圆桌论坛",
                            "speaker": "嘉宾信息待会议现场确认",
                            "affiliation": "",
                            "start": "16:10",
                            "end": profile["roundtableEnd"],
                            "badge": "圆桌论坛",
                            "sourcePage": 19,
                        }
                    ],
                },
            ],
        },
    ]

    source_note = (
        f"直接提取自{profile['editionLabel']}：{len(talks)} 场报告、{len(posters)} 张海报。"
    )
    if profile["expectedUpdateTitles"]:
        source_note += (
            f"{profile['expectedUpdateTitles']} 场报告题目原文为“更新中”；"
            "圆桌结束时间在总体表和详细表中不一致。"
        )
    else:
        source_note += "报告题目、报告人、会场与时间均按完整版更新。"

    conference = {
        "id": "microcavity-2026",
        "title": "2026 微腔光子学会议",
        "subtitle": f"{profile['editionLabel']}议程与海报名录",
        "dateRange": "2026年8月10日-12日",
        "location": profile["location"],
        "sourceNote": source_note,
        "talkCount": len(talks),
        "posterCount": len(posters),
        "days": days,
        "posters": posters,
    }
    return {
        "schemaVersion": 2,
        "generatedBy": "tools/import_microcavity_2026_pdf.py",
        "sourceDocument": pdf_path.name,
        "handbookEdition": profile["edition"],
        "importWarnings": profile["warnings"],
        "conferences": [conference],
    }


def validate_payload(
    payload: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    conference = payload["conferences"][0]
    all_items = [
        item
        for day in conference["days"]
        for session in day["sessions"]
        for item in session["items"]
    ]
    talks = [item for item in all_items if item["kind"] == "talk"]
    posters = conference["posters"]

    talk_ids = [talk["id"] for talk in talks]
    poster_ids = [poster["id"] for poster in posters]
    poster_codes = [poster["code"] for poster in posters]
    if len(talks) != profile["expectedTalks"]:
        raise ImportValidationError(
            f"Expected {profile['expectedTalks']} talks, found {len(talks)}"
        )
    if len(posters) != profile["expectedPosters"]:
        raise ImportValidationError(
            f"Expected {profile['expectedPosters']} posters, found {len(posters)}"
        )
    if len(set(talk_ids)) != len(talk_ids):
        raise ImportValidationError("Duplicate talk IDs")
    if len(set(poster_ids)) != len(poster_ids):
        raise ImportValidationError("Duplicate poster IDs")
    if len(set(poster_codes)) != len(poster_codes):
        raise ImportValidationError("Duplicate poster codes")

    missing_talk_fields = [
        talk["id"]
        for talk in talks
        if not all(talk.get(field) for field in ("title", "speaker", "affiliation", "start", "end"))
    ]
    if missing_talk_fields:
        raise ImportValidationError(f"Talks missing fields: {missing_talk_fields}")

    unresolved_authors: list[str] = []
    invalid_refs: list[str] = []
    for poster in posters:
        if not poster["title"] or not poster["authors"] or not poster["affiliations"]:
            raise ImportValidationError(f"Poster missing fields: {poster['code']}")
        valid_ids = {affiliation["id"] for affiliation in poster["affiliations"]}
        for author in poster["authors"]:
            if not author["affiliationIds"]:
                unresolved_authors.append(f"{poster['code']}:{author['name']}")
            elif not set(author["affiliationIds"]) <= valid_ids:
                invalid_refs.append(f"{poster['code']}:{author['name']}")
    if unresolved_authors:
        raise ImportValidationError(f"Unresolved author mappings: {unresolved_authors}")
    if invalid_refs:
        raise ImportValidationError(f"Invalid author mappings: {invalid_refs}")

    for day in conference["days"]:
        for session in day["sessions"]:
            timed = [
                item
                for item in session["items"]
                if item.get("start") and item.get("end") and item["kind"] == "talk"
            ]
            for previous, current in zip(timed, timed[1:]):
                if time_minutes(current["start"]) < time_minutes(previous["end"]):
                    raise ImportValidationError(
                        f"Overlapping talks in {session['id']}: {previous['id']} / {current['id']}"
                    )

    placeholders = [talk["id"] for talk in talks if talk["title"] == "更新中"]
    if len(placeholders) != profile["expectedUpdateTitles"]:
        raise ImportValidationError(
            f"Expected {profile['expectedUpdateTitles']} handbook '更新中' titles, "
            f"found {len(placeholders)}"
        )
    forbidden = ("待完整导入", "报告人待导入", "DEMO")
    serialized = json.dumps(payload, ensure_ascii=False)
    if any(value in serialized for value in forbidden):
        raise ImportValidationError("Generated JSON still contains prototype placeholders")

    return {
        "handbookEdition": profile["edition"],
        "talks": len(talks),
        "posters": len(posters),
        "posterAuthors": sum(len(poster["authors"]) for poster in posters),
        "correspondingAuthors": sum(
            author["corresponding"]
            for poster in posters
            for author in poster["authors"]
        ),
        "multiAffiliationPosters": sum(
            len(poster["affiliations"]) > 1 for poster in posters
        ),
        "unresolvedAuthorMappings": len(unresolved_authors),
        "handbookUpdateTitles": len(placeholders),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Parse and validate without writing the output JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = args.input_pdf.resolve()
    if not pdf_path.is_file():
        raise ImportValidationError(f"Input PDF not found: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        profile = EDITION_PROFILES.get(len(pdf.pages))
        if profile is None:
            raise ImportValidationError(
                "Unsupported handbook length: "
                f"{len(pdf.pages)} pages; expected 54-page first edition "
                "or 58-page complete edition"
            )
        overview = pdf.pages[11].extract_text(x_tolerance=2, y_tolerance=3) or ""
        detail = pdf.pages[18].extract_text(x_tolerance=2, y_tolerance=3) or ""
        expected_detail_end = (
            "16:10-17:30"
            if profile["edition"] == "first-edition"
            else "16:10-17:00"
        )
        if "16:10-17:00" not in overview or expected_detail_end not in detail:
            raise ImportValidationError(
                "Roundtable time did not match the detected handbook edition"
            )
        talks, session_metadata = extract_schedule(pdf, profile["schedulePages"])
        posters = extract_posters(pdf, profile["posterPages"])

    payload = build_payload(pdf_path, talks, session_metadata, posters, profile)
    summary = validate_payload(payload, profile)
    if not args.check_only:
        output_path = args.output_json.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output_path)
        summary["output"] = str(output_path)
    else:
        summary["output"] = None

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
