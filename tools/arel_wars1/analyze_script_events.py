#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from formats import parse_script_prefix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize recovered ZT1 script events")
    parser.add_argument("--catalog", type=Path, required=True, help="Path to recovery catalog.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the report JSON")
    return parser.parse_args()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def event_path_for(catalog_root: Path, decoded_path: str) -> Path:
    return catalog_root / decoded_path.replace(".bin", ".events.json")


def top_counter_items(counter: Counter[object], limit: int) -> list[dict[str, object]]:
    return [{"value": key, "count": count} for key, count in counter.most_common(limit)]


def main() -> None:
    args = parse_args()
    catalog_path = args.catalog.resolve()
    catalog_root = catalog_path.parent
    catalog = read_json(catalog_path)
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be a JSON object")

    zt1_entries = catalog.get("zt1Entries", [])
    if not isinstance(zt1_entries, list):
        raise ValueError("catalog is missing zt1Entries")

    locale_kind_counts: dict[str, Counter[str]] = defaultdict(Counter)
    speaker_tag_names: dict[int, Counter[str]] = defaultdict(Counter)
    prefix_counts: Counter[str] = Counter()
    prefix_samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    command_opcode_counts: Counter[str] = Counter()
    command_mnemonic_counts: Counter[str] = Counter()
    unknown_opcode_counts: Counter[str] = Counter()
    portrait_slot_usage: dict[str, Counter[int]] = defaultdict(Counter)
    portrait_slot_speakers: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_args: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_sequences: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_prev: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_next: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_speakers: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_speaker_tags: dict[str, Counter[int]] = defaultdict(Counter)
    unknown_command_scripts: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_command_samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    per_script: list[dict[str, object]] = []

    for entry in zt1_entries:
        if not isinstance(entry, dict) or entry.get("kind") != "script":
            continue

        decoded_path = str(entry.get("decodedPath", ""))
        events_path = event_path_for(catalog_root, decoded_path)
        if not events_path.exists():
            continue

        events = read_json(events_path)
        if not isinstance(events, list):
            continue

        locale = str(entry.get("locale") or "unknown")
        kind_counts = Counter()
        speaker_counts = Counter()
        for raw_event in events:
            if not isinstance(raw_event, dict):
                continue
            kind = str(raw_event.get("kind") or "unknown")
            kind_counts.update([kind])
            locale_kind_counts[locale].update([kind])

            speaker = raw_event.get("speaker")
            speaker_tag = raw_event.get("speakerTag")
            if isinstance(speaker, str):
                speaker_counts.update([speaker])
            if isinstance(speaker_tag, int) and isinstance(speaker, str):
                speaker_tag_names[speaker_tag].update([speaker])

            prefix_hex = str(raw_event.get("prefixHex") or "")
            if prefix_hex:
                prefix_counts.update([prefix_hex])
                samples = prefix_samples[prefix_hex]
                if len(samples) < 5:
                    samples.append(
                        {
                            "path": entry.get("path"),
                            "speaker": speaker,
                            "speakerTag": speaker_tag,
                            "text": raw_event.get("text"),
                        }
                    )
                prefix_parse = parse_script_prefix(prefix_hex)
                sequence = " > ".join(command.mnemonic for command in prefix_parse.commands)
                for command in prefix_parse.commands:
                    opcode_hex = f"{command.opcode:02x}"
                    command_opcode_counts.update([opcode_hex])
                    command_mnemonic_counts.update([command.mnemonic])
                    if command.mnemonic in {"set-left-portrait", "set-right-portrait"} and command.args:
                        portrait_slot_usage[command.mnemonic].update([command.args[0]])
                        if isinstance(speaker, str):
                            portrait_slot_speakers[command.mnemonic].update([f"{command.args[0]}:{speaker}"])
                for index, command in enumerate(prefix_parse.commands):
                    if not command.mnemonic.startswith("cmd-"):
                        continue
                    unknown_opcode_counts.update([command.mnemonic])
                    unknown_command_args[command.mnemonic].update(
                        [",".join(f"{value:02x}" for value in command.args) or "-"]
                    )
                    unknown_command_sequences[command.mnemonic].update([sequence])
                    unknown_command_prev[command.mnemonic].update(
                        [prefix_parse.commands[index - 1].mnemonic if index > 0 else "<start>"]
                    )
                    unknown_command_next[command.mnemonic].update(
                        [
                            prefix_parse.commands[index + 1].mnemonic
                            if index + 1 < len(prefix_parse.commands)
                            else "<end>"
                        ]
                    )
                    if isinstance(speaker, str):
                        unknown_command_speakers[command.mnemonic].update([speaker])
                    if isinstance(speaker_tag, int):
                        unknown_command_speaker_tags[command.mnemonic].update([speaker_tag])
                    entry_path = str(entry.get("path") or "")
                    if entry_path:
                        unknown_command_scripts[command.mnemonic].update([entry_path])
                    samples = unknown_command_samples[command.mnemonic]
                    if len(samples) < 8:
                        samples.append(
                            {
                                "path": entry.get("path"),
                                "speaker": speaker,
                                "speakerTag": speaker_tag,
                                "text": raw_event.get("text"),
                                "prefixHex": prefix_hex,
                                "sequence": sequence,
                                "args": list(command.args),
                            }
                        )

        per_script.append(
            {
                "path": entry.get("path"),
                "locale": entry.get("locale"),
                "eventCount": len(events),
                "kindCounts": dict(sorted(kind_counts.items())),
                "topSpeakers": [name for name, _count in speaker_counts.most_common(8)],
            }
        )

    report = {
        "scriptCount": len(per_script),
        "localeKindCounts": {
            locale: dict(sorted(counter.items()))
            for locale, counter in sorted(locale_kind_counts.items())
        },
        "speakerTagDirectory": [
            {
                "speakerTag": speaker_tag,
                "topNames": [name for name, _count in counter.most_common(10)],
                "sampleCount": sum(counter.values()),
            }
            for speaker_tag, counter in sorted(speaker_tag_names.items())
        ],
        "prefixPatterns": [
            {
                "prefixHex": prefix_hex,
                "count": count,
                "parsedCommands": [
                    {
                        "opcode": command.opcode,
                        "args": list(command.args),
                        "mnemonic": command.mnemonic,
                    }
                    for command in parse_script_prefix(prefix_hex).commands
                ],
                "trailingHex": parse_script_prefix(prefix_hex).trailing_hex,
                "samples": prefix_samples[prefix_hex],
            }
            for prefix_hex, count in prefix_counts.most_common(24)
        ],
        "prefixOpcodeCounts": dict(sorted(command_opcode_counts.items())),
        "prefixMnemonicCounts": dict(sorted(command_mnemonic_counts.items())),
        "portraitCommandHints": {
            slot: {
                "portraitIds": dict(sorted(counter.items())),
                "speakerHints": dict(sorted(portrait_slot_speakers.get(slot, Counter()).most_common(24))),
            }
            for slot, counter in sorted(portrait_slot_usage.items())
        },
        "unknownCommandProfiles": [
            {
                "mnemonic": mnemonic,
                "count": count,
                "topArgs": top_counter_items(unknown_command_args[mnemonic], 8),
                "topSequences": top_counter_items(unknown_command_sequences[mnemonic], 8),
                "previousCommands": top_counter_items(unknown_command_prev[mnemonic], 8),
                "nextCommands": top_counter_items(unknown_command_next[mnemonic], 8),
                "topSpeakers": top_counter_items(unknown_command_speakers[mnemonic], 8),
                "topSpeakerTags": top_counter_items(unknown_command_speaker_tags[mnemonic], 8),
                "topScripts": top_counter_items(unknown_command_scripts[mnemonic], 8),
                "samples": unknown_command_samples[mnemonic],
            }
            for mnemonic, count in unknown_opcode_counts.most_common()
        ],
        "topScripts": sorted(per_script, key=lambda item: int(item["eventCount"]), reverse=True)[:32],
    }

    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
