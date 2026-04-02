#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import struct


TOKEN_RE = re.compile(r"[A-Za-z']+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a provisional AW1 stage/script correlation report")
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables",
    )
    parser.add_argument(
        "--script-root",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/decoded/zt1/assets/script_eng",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the correlation JSON",
    )
    return parser.parse_args()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_tokens(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(text.lower()):
        if token in STOPWORDS or len(token) < 2:
            continue
        tokens.append(token)
    return tokens


def classify_ai_row(title: str, has_script_family: bool) -> str:
    if has_script_family:
        return "script-backed-stage"
    lowered = title.lower()
    if any(token in lowered for token in ("aggressive", "defensive", "progressive")):
        return "ai-preset"
    if any(token in lowered for token in ("very poor", "poor", "normal", "rich")):
        return "ai-preset"
    if title:
        return "battle-only-or-unused"
    return "unknown"


def runtime_field_candidates(ai_record: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(ai_record, dict):
        return None
    numeric_block_hex = ai_record.get("numericBlockHex")
    if not isinstance(numeric_block_hex, str):
        return None
    blob = bytes.fromhex(numeric_block_hex)
    if len(blob) < 20:
        return None
    return {
        "blobPrefixHex": blob[:20].hex(),
        "stageScalarCandidate": struct.unpack_from("<I", blob, 8)[0],
        "tierCandidate": blob[13],
        "variantCandidate": blob[15],
        "regionCandidate": blob[16],
        "constantMarkerCandidate": blob[17],
        "storyFlagCandidate": blob[18],
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    script_root = args.script_root.resolve()

    ai_report = read_json(parsed_dir / "XlsAi.eng.parsed.json")
    summary = read_json(parsed_dir / "AW1.gxl.summary.json")
    if not isinstance(ai_report, dict) or not isinstance(summary, dict):
        raise ValueError("parsed reports are not JSON objects")

    ai_records = ai_report.get("records", [])
    if not isinstance(ai_records, list):
        raise ValueError("XlsAi report is missing records")

    family_files: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(script_root.glob("*.events.json")):
        stem = path.name.replace(".zt1.events.json", "")
        family_files[stem[:3]].append(path)

    families: list[dict[str, object]] = []
    for family_id in sorted(family_files):
        files = family_files[family_id]
        family_texts: list[str] = []
        event_count = 0
        event_previews: list[dict[str, object]] = []
        unique_speakers: dict[str, int] = defaultdict(int)

        for path in files:
            events = read_json(path)
            if not isinstance(events, list):
                continue
            event_count += len(events)
            for event in events:
                if not isinstance(event, dict):
                    continue
                text = str(event.get("text") or "")
                if text:
                    family_texts.append(text)
                speaker = event.get("speaker")
                if isinstance(speaker, str) and speaker:
                    unique_speakers[speaker] += 1
            if len(event_previews) < 4:
                preview_texts = [
                    str(event.get("text") or "")
                    for event in events
                    if isinstance(event, dict) and event.get("text")
                ][:4]
                event_previews.append(
                    {
                        "file": path.name,
                        "previewTexts": preview_texts,
                    }
                )

        family_blob = " ".join(family_texts)
        family_tokens = set(normalize_tokens(family_blob))
        ai_index = int(family_id)
        ai_record = ai_records[ai_index] if ai_index < len(ai_records) else None

        title_overlap: list[str] = []
        reward_overlap: list[str] = []
        hint_overlap: list[str] = []
        title = None
        reward = None
        hint = None
        if isinstance(ai_record, dict):
            title = str(ai_record.get("title") or "")
            reward = str(ai_record.get("rewardText") or "")
            hint = str(ai_record.get("hintText") or "")
            title_overlap = sorted(set(normalize_tokens(title)) & family_tokens)
            reward_overlap = sorted(set(normalize_tokens(reward)) & family_tokens)
            hint_overlap = sorted(set(normalize_tokens(hint)) & family_tokens)

        families.append(
            {
                "familyId": family_id,
                "scriptFiles": [path.name for path in files],
                "scriptFileCount": len(files),
                "eventCount": event_count,
                "topSpeakers": sorted(
                    unique_speakers.items(), key=lambda item: item[1], reverse=True
                )[:8],
                "preview": event_previews,
                "aiIndexCandidate": ai_index,
                "aiTitleCandidate": title,
                "aiRewardCandidate": reward,
                "aiHintCandidate": hint,
                "runtimeFieldCandidates": runtime_field_candidates(ai_record),
                "titleTokenOverlap": title_overlap,
                "rewardTokenOverlap": reward_overlap,
                "hintTokenOverlap": hint_overlap,
            }
        )

    ai_without_script = []
    for index, record in enumerate(ai_records):
        family_id = f"{index:03d}"
        if family_id in family_files:
            continue
        title = str(record.get("title") or "")
        ai_without_script.append(
            {
                "aiIndex": index,
                "title": title,
                "kindGuess": classify_ai_row(title, has_script_family=False),
                "runtimeFieldCandidates": runtime_field_candidates(record),
            }
        )

    kind_histogram: dict[str, int] = defaultdict(int)
    for item in ai_without_script:
        kind_histogram[str(item["kindGuess"])] += 1

    report = {
        "scriptFamilyCount": len(families),
        "aiRowCount": len(ai_records),
        "worldmapIsLinearChain": summary.get("worldmap", {}).get("isLinearChain"),
        "scriptBackedAiRowCount": len(ai_records) - len(ai_without_script),
        "aiRowsWithoutScriptFamilyByKind": dict(sorted(kind_histogram.items())),
        "families": families,
        "aiRowsWithoutScriptFamily": ai_without_script,
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
