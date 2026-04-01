#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil


FEATURED_TIMELINE_ORDER = [
    "rising-anchor-with-overlays",
    "rising-anchor-run",
    "single-anchor-with-overlays",
    "single-anchor-cadence",
    "mixed-anchor-overlay",
    "overlay-track-only",
    "linked-only-scatter",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export recovery preview assets into the web runtime root")
    parser.add_argument("--report", type=Path, required=True, help="Path to binary_asset_report.json")
    parser.add_argument("--sequence-root", type=Path, required=True, help="Path to frame_sequence_candidates")
    parser.add_argument("--timeline-root", type=Path, required=True, help="Path to timeline_candidate_strips")
    parser.add_argument("--web-root", type=Path, required=True, help="Path to public web recovery root")
    return parser.parse_args()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def pick_featured_stems(entries: list[dict[str, object]]) -> list[str]:
    by_timeline: dict[str, list[str]] = {}
    for entry in entries:
        by_timeline.setdefault(str(entry["timelineKind"]), []).append(str(entry["stem"]))

    featured: list[str] = []
    for timeline_kind in FEATURED_TIMELINE_ORDER:
        stem_list = sorted(by_timeline.get(timeline_kind, []))
        if not stem_list:
            continue
        featured.append(stem_list[0])

    if len(featured) < min(6, len(entries)):
        for entry in sorted(entries, key=lambda item: (str(item["timelineKind"]), str(item["stem"]))):
            stem = str(entry["stem"])
            if stem not in featured:
                featured.append(stem)
            if len(featured) >= 6:
                break

    return featured


def main() -> None:
    args = parse_args()
    report_path = args.report.resolve()
    sequence_root = args.sequence_root.resolve()
    timeline_root = args.timeline_root.resolve()
    web_root = args.web_root.resolve()

    report = read_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("binary asset report is not a JSON object")

    active_entries: list[dict[str, object]] = []
    pzx_entries = report.get("pzx", [])
    if not isinstance(pzx_entries, list):
        raise ValueError("binary asset report is missing pzx entries")

    for entry in pzx_entries:
        if not isinstance(entry, dict):
            continue
        path = Path(str(entry.get("path", "")))
        frame_streams = entry.get("frameRecordStreams", [])
        if not isinstance(frame_streams, list):
            continue
        for stream in frame_streams:
            if not isinstance(stream, dict):
                continue
            sequence_summary = stream.get("metaSequenceSummary")
            if not isinstance(sequence_summary, dict):
                continue
            sequence_kind = str(sequence_summary.get("sequenceKind", ""))
            if sequence_kind == "no-sequence-candidates":
                continue

            stem = path.stem
            timeline_strip_png = timeline_root / f"{stem}-timeline-strip.png"
            timeline_strip_json = timeline_root / f"{stem}-timeline-strip.json"
            sequence_summary_json = sequence_root / f"{stem}-sequence-summary.json"
            linked_png = sequence_root / f"{stem}-linked-sequence.png"
            overlay_png = sequence_root / f"{stem}-overlay-sequence.png"

            if not timeline_strip_png.exists() or not timeline_strip_json.exists() or not sequence_summary_json.exists():
                continue

            active_entries.append(
                {
                    "stem": stem,
                    "sequenceKind": sequence_kind,
                    "timelineKind": str(sequence_summary.get("timelineKind", "unknown")),
                    "anchorFrameSequence": sequence_summary.get("anchorFrameSequence", []),
                    "linkedGroupCount": int(sequence_summary.get("linkedGroupCount", 0)),
                    "overlayGroupCount": int(sequence_summary.get("overlayGroupCount", 0)),
                    "bestContiguousRun": sequence_summary.get("bestContiguousRun"),
                    "timelineStripSourcePng": timeline_strip_png,
                    "timelineStripSourceJson": timeline_strip_json,
                    "sequenceSummarySourceJson": sequence_summary_json,
                    "linkedSourcePng": linked_png if linked_png.exists() else None,
                    "overlaySourcePng": overlay_png if overlay_png.exists() else None,
                }
            )
            break

    featured_stems = pick_featured_stems(active_entries)

    analysis_root = web_root / "analysis"
    timeline_target_root = analysis_root / "timeline_candidate_strips"
    sequence_target_root = analysis_root / "frame_sequence_candidates"
    ensure_paths = [timeline_target_root, sequence_target_root]
    for path in ensure_paths:
        path.mkdir(parents=True, exist_ok=True)

    exported_entries: list[dict[str, object]] = []
    sequence_counts = Counter()
    timeline_counts = Counter()
    for entry in sorted(active_entries, key=lambda item: str(item["stem"])):
        stem = str(entry["stem"])
        sequence_kind = str(entry["sequenceKind"])
        timeline_kind = str(entry["timelineKind"])
        sequence_counts.update([sequence_kind])
        timeline_counts.update([timeline_kind])

        timeline_png_name = f"{stem}-timeline-strip.png"
        timeline_json_name = f"{stem}-timeline-strip.json"
        sequence_json_name = f"{stem}-sequence-summary.json"
        linked_name = f"{stem}-linked-sequence.png"
        overlay_name = f"{stem}-overlay-sequence.png"

        copy_file(Path(entry["timelineStripSourcePng"]), timeline_target_root / timeline_png_name)
        copy_file(Path(entry["timelineStripSourceJson"]), timeline_target_root / timeline_json_name)
        copy_file(Path(entry["sequenceSummarySourceJson"]), sequence_target_root / sequence_json_name)
        if entry["linkedSourcePng"] is not None:
            copy_file(Path(entry["linkedSourcePng"]), sequence_target_root / linked_name)
        if entry["overlaySourcePng"] is not None:
            copy_file(Path(entry["overlaySourcePng"]), sequence_target_root / overlay_name)

        exported_entries.append(
            {
                "stem": stem,
                "sequenceKind": sequence_kind,
                "timelineKind": timeline_kind,
                "anchorFrameSequence": entry["anchorFrameSequence"],
                "linkedGroupCount": int(entry["linkedGroupCount"]),
                "overlayGroupCount": int(entry["overlayGroupCount"]),
                "bestContiguousRun": entry["bestContiguousRun"],
                "timelineStrip": {
                    "pngPath": f"/recovery/analysis/timeline_candidate_strips/{timeline_png_name}",
                    "jsonPath": f"/recovery/analysis/timeline_candidate_strips/{timeline_json_name}",
                },
                "sequenceSummaryPath": f"/recovery/analysis/frame_sequence_candidates/{sequence_json_name}",
                "linkedSequencePngPath": (
                    f"/recovery/analysis/frame_sequence_candidates/{linked_name}" if entry["linkedSourcePng"] is not None else None
                ),
                "overlaySequencePngPath": (
                    f"/recovery/analysis/frame_sequence_candidates/{overlay_name}" if entry["overlaySourcePng"] is not None else None
                ),
            }
        )

    featured_entries = [entry for entry in exported_entries if str(entry["stem"]) in featured_stems]
    manifest = {
        "generatedAt": report.get("summary", {}).get("generatedAt") or report.get("generatedAt"),
        "activeStemCount": len(exported_entries),
        "sequenceKindCounts": dict(sorted(sequence_counts.items())),
        "timelineKindCounts": dict(sorted(timeline_counts.items())),
        "featuredStems": featured_stems,
        "featuredEntries": featured_entries,
        "stems": exported_entries,
    }

    write_json(analysis_root / "preview_manifest.json", manifest)


if __name__ == "__main__":
    main()
