#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_heuristics import (
    OPCODE_ACTION_OVERRIDES,
    OPCODE_VARIANT_OVERRIDES,
    RUNTIME_FEATURED_MNEMONICS,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a structured AW1 opcode action map from script-event clustering data"
    )
    parser.add_argument(
        "--script-report",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/script_event_report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write AW1.opcode_action_map.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def counter_preview(values: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for item in values[:limit]:
        if not isinstance(item, dict):
            continue
        preview.append(
            {
                "value": item.get("value"),
                "count": int(item.get("count", 0)),
            }
        )
    return preview


def sample_preview(values: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for item in values[:limit]:
        if not isinstance(item, dict):
            continue
        preview.append(
            {
                "path": item.get("path"),
                "speaker": item.get("speaker"),
                "text": item.get("text"),
                "sequence": item.get("sequence"),
            }
        )
    return preview


def signal_sentence(profile: dict[str, Any]) -> str:
    previous = profile.get("previousCommands", [])
    following = profile.get("nextCommands", [])
    prev_value = previous[0]["value"] if previous else None
    prev_count = int(previous[0]["count"]) if previous else 0
    next_value = following[0]["value"] if following else None
    next_count = int(following[0]["count"]) if following else 0
    if prev_value is None and next_value is None:
        return "No stable surrounding-command signal yet."
    if prev_value is None:
        return f"Most common follower is `{next_value}` ({next_count}x)."
    if next_value is None:
        return f"Most common predecessor is `{prev_value}` ({prev_count}x)."
    return f"Most common predecessor/follower is `{prev_value}` ({prev_count}x) -> `{next_value}` ({next_count}x)."


def variant_evidence_sentence(variant: dict[str, Any]) -> str:
    scripts = variant.get("topScripts", [])
    tokens = variant.get("topEnglishTokens", [])
    parts: list[str] = []
    if scripts:
        parts.append(f"Top script is `{scripts[0]['value']}`.")
    if tokens:
        token_values = [str(item["value"]) for item in tokens[:3]]
        parts.append(f"Top English tokens: {', '.join(token_values)}.")
    return " ".join(parts) if parts else "No strong variant-local text tokens yet."


def build_variant_hints(
    variants: list[dict[str, Any]], mnemonic: str
) -> list[dict[str, Any]]:
    by_mnemonic = [item for item in variants if item.get("mnemonic") == mnemonic]
    curated: list[dict[str, Any]] = []
    for item in by_mnemonic:
        variant_key = str(item.get("variant"))
        override = OPCODE_VARIANT_OVERRIDES.get(variant_key)
        if override is None:
            continue
        curated.append(
            {
                "variant": variant_key,
                "args": list(item.get("args", [])),
                "label": override["label"],
                "action": override["action"],
                "category": override["category"],
                "confidence": override["confidence"],
                "count": int(item.get("count", 0)),
                "evidenceSummary": [
                    variant_evidence_sentence(item),
                    *override.get("notes", []),
                ],
                "topScripts": counter_preview(item.get("topScripts", []), limit=4),
                "topEnglishTokens": counter_preview(item.get("topEnglishTokens", []), limit=6),
                "samples": sample_preview(item.get("samples", []), limit=3),
            }
        )
    curated.sort(key=lambda entry: (-int(entry["count"]), str(entry["variant"])))
    return curated


def main() -> None:
    args = parse_args()
    report = read_json(args.script_report.resolve())
    profiles = report.get("unknownCommandProfiles", [])
    variants = report.get("unknownCommandVariants", [])

    opcode_actions: list[dict[str, Any]] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        mnemonic = str(profile.get("mnemonic") or "")
        if not mnemonic:
            continue
        override = OPCODE_ACTION_OVERRIDES.get(mnemonic, {})
        variant_hints = build_variant_hints(variants, mnemonic)
        evidence = [
            signal_sentence(profile),
            *override.get("notes", []),
        ]
        opcode_actions.append(
            {
                "mnemonic": mnemonic,
                "label": override.get("label", mnemonic),
                "action": override.get("action", "unknown-runtime-action"),
                "category": override.get("category", "unknown"),
                "confidence": override.get("confidence", "low"),
                "count": int(profile.get("count", 0)),
                "featuredInRuntime": mnemonic in RUNTIME_FEATURED_MNEMONICS,
                "evidenceSummary": evidence,
                "variantHints": variant_hints,
                "signalProfile": {
                    "topArgs": counter_preview(profile.get("topArgs", []), limit=6),
                    "topSequences": counter_preview(profile.get("topSequences", []), limit=6),
                    "previousCommands": counter_preview(profile.get("previousCommands", []), limit=6),
                    "nextCommands": counter_preview(profile.get("nextCommands", []), limit=6),
                    "topSpeakers": counter_preview(profile.get("topSpeakers", []), limit=6),
                    "topScripts": counter_preview(profile.get("topScripts", []), limit=6),
                    "samples": sample_preview(profile.get("samples", []), limit=4),
                },
            }
        )

    opcode_actions.sort(
        key=lambda item: (
            0 if bool(item["featuredInRuntime"]) else 1,
            -int(item["count"]),
            str(item["mnemonic"]),
        )
    )

    featured_actions = [item for item in opcode_actions if bool(item["featuredInRuntime"])]
    findings = [
        "Opcode action export now separates mnemonic-wide hints from variant-local clues so runtime labels no longer depend on exporter-local constants.",
        "The strongest tutorial/UI variants remain cmd-06(0x0d), cmd-07(0x40), cmd-0a(0x40), and cmd-0c(0x40).",
        "The strongest presentation/emphasis variants remain cmd-05(0x03), cmd-08(0x00), cmd-0a(0x10), and cmd-0b(0x10).",
    ]
    payload = {
        "summary": {
            "opcodeActionCount": len(opcode_actions),
            "featuredOpcodeCount": len(featured_actions),
            "curatedVariantCount": sum(len(item["variantHints"]) for item in opcode_actions),
        },
        "opcodeActions": opcode_actions,
        "featuredOpcodeActions": featured_actions,
        "findings": findings,
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
