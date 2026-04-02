#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import struct
import sys
import zipfile


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from formats import extract_strings, read_zt1  # noqa: E402

try:
    from formats import extract_script_events, parse_script_prefix  # type: ignore[attr-defined]  # noqa: E402
except ImportError:
    SCRIPT_PREFIX_MNEMONICS: dict[int, str] = {
        0x01: "set-right-portrait",
        0x03: "set-left-portrait",
        0x04: "set-expression",
        0x05: "cmd-05",
        0x06: "cmd-06",
        0x07: "cmd-07",
        0x08: "cmd-08",
        0x09: "cmd-09",
        0x0A: "cmd-0a",
        0x0B: "cmd-0b",
    }
    SCRIPT_PREFIX_ARG_COUNTS: dict[int, int] = {
        0x01: 2,
        0x03: 2,
    }

    @dataclass(frozen=True)
    class ScriptEvent:
        offset: int
        kind: str
        prefix_hex: str
        speaker: str | None
        speaker_tag: int | None
        text: str
        byte_length: int

    @dataclass(frozen=True)
    class ScriptPrefixCommand:
        opcode: int
        args: tuple[int, ...]
        mnemonic: str

    @dataclass(frozen=True)
    class ScriptPrefixParse:
        commands: tuple[ScriptPrefixCommand, ...]
        trailing_hex: str | None

    def parse_script_prefix(prefix: bytes | str) -> ScriptPrefixParse:
        if isinstance(prefix, str):
            prefix_bytes = bytes.fromhex(prefix) if prefix else b""
        else:
            prefix_bytes = prefix

        commands: list[ScriptPrefixCommand] = []
        cursor = 0
        while cursor < len(prefix_bytes):
            if prefix_bytes[cursor] == 0x00 and cursor == len(prefix_bytes) - 1:
                cursor += 1
                break
            opcode = prefix_bytes[cursor]
            arg_count = SCRIPT_PREFIX_ARG_COUNTS.get(opcode, 1)
            next_cursor = cursor + 1 + arg_count
            if next_cursor > len(prefix_bytes):
                break
            commands.append(
                ScriptPrefixCommand(
                    opcode=opcode,
                    args=tuple(prefix_bytes[cursor + 1 : next_cursor]),
                    mnemonic=SCRIPT_PREFIX_MNEMONICS.get(opcode, f"cmd-{opcode:02x}"),
                )
            )
            cursor = next_cursor

        trailing = prefix_bytes[cursor:].hex() if cursor < len(prefix_bytes) else None
        return ScriptPrefixParse(commands=tuple(commands), trailing_hex=trailing or None)

    def _decode_script_text(data: bytes, encoding: str) -> str | None:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            return None
        if not text:
            return None
        printable = sum(1 for char in text if char.isprintable() and char not in "\x0b\x0c")
        if printable / len(text) < 0.95:
            return None
        return text

    def _looks_like_script_speaker(text: str) -> bool:
        stripped = text.strip()
        if not stripped or len(stripped) > 24:
            return False
        allowed_punctuation = set(" .'!-&*/()")
        if not all(char.isalnum() or ("\uac00" <= char <= "\ud7a3") or char in allowed_punctuation for char in stripped):
            return False
        alpha_count = sum(1 for char in stripped if char.isalnum() or ("\uac00" <= char <= "\ud7a3"))
        return alpha_count >= 2

    def _looks_like_script_body(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if any(char.isalnum() or ("\uac00" <= char <= "\ud7a3") for char in stripped):
            return True
        return all(char in ".!?…" for char in stripped.replace(" ", ""))

    def _is_ascii_printable_byte(value: int) -> bool:
        return 0x20 <= value <= 0x7E

    def _ascii_runs(prefix_bytes: bytes) -> list[tuple[int, int]]:
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for index, value in enumerate(prefix_bytes):
            if _is_ascii_printable_byte(value):
                if start is None:
                    start = index
                continue
            if start is not None and index - start >= 4:
                runs.append((start, index))
            start = None
        if start is not None and len(prefix_bytes) - start >= 4:
            runs.append((start, len(prefix_bytes)))
        return runs

    def _sanitize_script_prefix(prefix_bytes: bytes) -> bytes:
        if not prefix_bytes:
            return prefix_bytes
        best_prefix = b""
        best_score = float("-inf")
        candidate_roots = {prefix_bytes}
        for run_start, run_end in _ascii_runs(prefix_bytes):
            candidate_roots.add(prefix_bytes[:run_start] + prefix_bytes[run_end:])
        for root in candidate_roots:
            for start in range(0, len(root) + 1):
                candidate = root[start:]
                if not candidate:
                    score = 0.25
                else:
                    parsed = parse_script_prefix(candidate)
                    score = 0.0
                    known_command_count = 0
                    high_ascii_command_count = 0
                    for command in parsed.commands:
                        if command.mnemonic in {"set-left-portrait", "set-right-portrait", "set-expression"}:
                            score += 5.0
                            known_command_count += 1
                        elif command.opcode <= 0x1F:
                            score += 2.0
                        elif command.opcode <= 0x43:
                            score += 1.0
                        else:
                            score -= 0.75
                        if command.args:
                            if all(arg <= 0x40 for arg in command.args):
                                score += 0.5
                            if all(_is_ascii_printable_byte(arg) for arg in command.args):
                                score -= 0.75
                                if command.opcode >= 0x20:
                                    high_ascii_command_count += 1
                    printable_ratio = sum(1 for byte in candidate if _is_ascii_printable_byte(byte)) / len(candidate)
                    if printable_ratio >= 0.7:
                        score -= printable_ratio * 3.5
                    if known_command_count == 0 and high_ascii_command_count >= max(2, len(parsed.commands) // 2):
                        score -= 6.0
                    if parsed.trailing_hex:
                        score -= len(parsed.trailing_hex) / 2
                    score -= start * 0.02
                    score -= max(len(prefix_bytes) - len(root), 0) * 0.03
                if score > best_score:
                    best_score = score
                    best_prefix = candidate
        return best_prefix

    def _parse_script_events_with_encoding(data: bytes, encoding: str) -> list[ScriptEvent]:
        events: list[ScriptEvent] = []
        offset = 0
        while offset < len(data):
            if data[offset] == 0xFF and offset + 3 <= len(data):
                text_len = struct.unpack("<H", data[offset + 1 : offset + 3])[0]
                text_end = offset + 3 + text_len
                if 1 <= text_len <= 800 and text_end <= len(data):
                    text = _decode_script_text(data[offset + 3 : text_end], encoding)
                    if text is not None and _looks_like_script_body(text):
                        event_end = text_end
                        while event_end < len(data) and data[event_end] == 0:
                            event_end += 1
                        events.append(
                            ScriptEvent(
                                offset=offset,
                                kind="caption",
                                prefix_hex="ff",
                                speaker=None,
                                speaker_tag=None,
                                text=text,
                                byte_length=event_end - offset,
                            )
                        )
                        offset = event_end
                        continue

            matched_event: ScriptEvent | None = None
            matched_end = offset + 1
            for gap in range(0, 16):
                payload_offset = offset + gap
                if payload_offset + 2 > len(data):
                    break
                speaker_len = struct.unpack("<H", data[payload_offset : payload_offset + 2])[0]
                if not 2 <= speaker_len <= 16:
                    continue
                speaker_start = payload_offset + 2
                speaker_end = speaker_start + speaker_len
                if speaker_end + 3 > len(data):
                    continue
                speaker = _decode_script_text(data[speaker_start:speaker_end], encoding)
                if speaker is None or not _looks_like_script_speaker(speaker):
                    continue
                speaker_tag = data[speaker_end]
                text_len = struct.unpack("<H", data[speaker_end + 1 : speaker_end + 3])[0]
                if not 1 <= text_len <= 800:
                    continue
                text_start = speaker_end + 3
                text_end = text_start + text_len
                if text_end > len(data):
                    continue
                text = _decode_script_text(data[text_start:text_end], encoding)
                if text is None or not _looks_like_script_body(text):
                    continue
                matched_event = ScriptEvent(
                    offset=offset,
                    kind="speech",
                    prefix_hex=_sanitize_script_prefix(data[offset:payload_offset]).hex(),
                    speaker=speaker,
                    speaker_tag=speaker_tag,
                    text=text,
                    byte_length=text_end - offset,
                )
                matched_end = text_end
                break

            if matched_event is not None:
                events.append(matched_event)
                offset = matched_end
                continue
            offset += 1
        return events

    def extract_script_events(
        data: bytes,
        preferred_encoding: str | None = None,
    ) -> tuple[str | None, tuple[ScriptEvent, ...]]:
        encodings: list[str] = []
        if preferred_encoding is not None:
            encodings.append(preferred_encoding)
        for fallback in ("utf-8", "cp949"):
            if fallback not in encodings:
                encodings.append(fallback)
        best_encoding: str | None = None
        best_events: list[ScriptEvent] = []
        best_score = -1
        for encoding in encodings:
            events = _parse_script_events_with_encoding(data, encoding)
            if not events:
                continue
            score = len(events) * 100 + sum(len(event.text) for event in events)
            if score > best_score:
                best_score = score
                best_encoding = encoding
                best_events = events
        return (best_encoding, tuple(best_events))


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
