#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import zipfile


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from formats import extract_script_events, extract_strings, parse_script_prefix, read_zt1  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover and catalog assets from arel_wars_2.apk")
    parser.add_argument("--apk", type=Path, required=True, help="Path to arel_wars_2.apk")
    parser.add_argument("--output", type=Path, required=True, help="Directory for recovery artifacts")
    return parser.parse_args()


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def copy_member(zf: zipfile.ZipFile, member: str, root: Path) -> Path:
    target = root / member
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return target


def preferred_encoding_for(member: str) -> str | None:
    if member.startswith("assets/"):
        return "utf-8"
    return None


def locale_for(member: str) -> str | None:
    if "/eng/" in member:
        return "en"
    if "/kor/" in member:
        return "ko"
    if "/jpn/" in member:
        return "ja"
    return None


def kind_for(member: str) -> str:
    if "/script/" in member:
        return "script"
    if "/table/" in member:
        return "table"
    if "/map/" in member:
        return "map"
    return "unknown"


def main() -> None:
    args = parse_args()
    apk_path = args.apk.resolve()
    output_root = args.output.resolve()
    apk_unzip_root = output_root / "apk_unzip"
    decoded_root = output_root / "decoded" / "zt1"

    ensure_clean_dir(apk_unzip_root)
    ensure_clean_dir(decoded_root)

    ext_counts: Counter[str] = Counter()
    asset_dir_counts: Counter[str] = Counter()
    zt1_entries: list[dict[str, object]] = []

    with zipfile.ZipFile(apk_path) as zf:
        for member in sorted(zf.namelist()):
            suffix = Path(member).suffix.lower() or "<none>"
            ext_counts[suffix] += 1
            if member.startswith("assets/") and "/" in member[7:]:
                asset_dir_counts[member.split("/")[1]] += 1

            copied_path = copy_member(zf, member, apk_unzip_root)
            if suffix != ".zt1":
                continue

            decoded = read_zt1(copied_path.read_bytes())
            decoded_path = decoded_root / f"{member}.bin"
            decoded_path.parent.mkdir(parents=True, exist_ok=True)
            decoded_path.write_bytes(decoded.decoded)

            preferred_encoding = preferred_encoding_for(member)
            guessed_encoding, strings = extract_strings(decoded.decoded, preferred_encoding=preferred_encoding)
            script_encoding, script_events = (
                extract_script_events(decoded.decoded, preferred_encoding=preferred_encoding)
                if kind_for(member) == "script"
                else (None, ())
            )

            entry = {
                "path": member,
                "kind": kind_for(member),
                "locale": locale_for(member),
                "packedSize": decoded.packed_size,
                "decodedSize": decoded.unpacked_size,
                "encoding": guessed_encoding,
                "scriptEncoding": script_encoding,
                "stringCount": len(strings),
                "stringsPreview": strings[:12],
                "eventCount": len(script_events),
                "eventPreview": [
                    {
                        "kind": event.kind,
                        "prefixHex": event.prefix_hex,
                        "speaker": event.speaker,
                        "speakerTag": event.speaker_tag,
                        "text": event.text,
                    }
                    for event in script_events[:8]
                ],
                "decodedPath": str(decoded_path.relative_to(output_root)),
            }
            zt1_entries.append(entry)

            if strings:
                write_text(decoded_root / f"{member}.strings.txt", "\n".join(strings))
            if script_events:
                events_path = decoded_root / f"{member}.events.json"
                write_json(
                    events_path,
                    [
                        {
                            "offset": event.offset,
                            "kind": event.kind,
                            "prefixHex": event.prefix_hex,
                            "prefixCommands": [
                                {
                                    "opcode": command.opcode,
                                    "args": list(command.args),
                                    "mnemonic": command.mnemonic,
                                }
                                for command in prefix_parse.commands
                            ],
                            "prefixTrailingHex": prefix_parse.trailing_hex,
                            "speaker": event.speaker,
                            "speakerTag": event.speaker_tag,
                            "text": event.text,
                            "byteLength": event.byte_length,
                        }
                        for event in script_events
                        for prefix_parse in [parse_script_prefix(event.prefix_hex)]
                    ],
                )
                entry["eventsPath"] = str(events_path.relative_to(output_root))

    featured_scripts = sorted(
        (entry for entry in zt1_entries if entry["kind"] == "script"),
        key=lambda item: (int(item["eventCount"]), int(item["decodedSize"])),
        reverse=True,
    )[:24]

    catalog = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "apkPath": str(apk_path),
        "inventory": {
            "extensions": dict(sorted(ext_counts.items())),
            "assetDirectories": dict(sorted(asset_dir_counts.items())),
            "zt1Total": len(zt1_entries),
            "scriptEventTotal": sum(int(entry["eventCount"]) for entry in zt1_entries if entry["kind"] == "script"),
        },
        "featuredScripts": featured_scripts,
        "blockedFormats": [
            {
                "suffix": suffix,
                "count": ext_counts[suffix],
                "reason": reason,
            }
            for suffix, reason in (
                (".pzx", "AW2 uses a different PZX container shape from AW1; row streams decode, outer table semantics still differ."),
                (".pzd", "AW2 body-part sprites now decode as multi-stream row-RLE containers, but frame/state semantics still depend on PZF."),
                (".pzf", "AW2 PZF exposes a big-endian offset table plus one large metadata zlib stream; record semantics are still being inferred."),
                (".mpl", "AW2 MPL is not the AW1 two-bank palette format and remains mostly a stub/sidecar file."),
                (".ptc", "PTC parses structurally, but field semantics remain heuristic."),
            )
            if suffix in ext_counts
        ],
        "zt1Entries": zt1_entries,
    }
    write_json(output_root / "catalog.json", catalog)


if __name__ == "__main__":
    main()
