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


def first_counter_value(values: list[dict[str, Any]]) -> str | None:
    if not values:
        return None
    value = values[0].get("value")
    return None if value is None else str(value)


def first_arg_slug(args: list[Any]) -> str:
    if not args:
        return "00"
    parts: list[str] = []
    for value in args:
        if isinstance(value, int):
            parts.append(f"{value:02x}")
            continue
        text = str(value).strip().lower()
        if not text:
            continue
        parts.append(text)
    return "-".join(parts) if parts else "00"


def slugify_suffix(value: str) -> str:
    return value.lower().replace(",", "-")


def build_scene_fields(
    *,
    label: str,
    action: str,
    category: str,
    confidence: str,
    command_id: str | None = None,
    command_type: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    lowered_action = action.lower()

    if command_type is None:
        if category == "presentation":
            command_type = "presentation"
        elif category == "emphasis":
            command_type = "emphasis"
        elif category == "scene-bootstrap":
            command_type = "scene-layout"
        elif "tutorial" in lowered_action and "narration" in lowered_action:
            command_type = "tutorial-mode"
        elif "focus" in lowered_action or "highlight" in lowered_action or "anchor" in lowered_action or "bind" in lowered_action:
            command_type = "ui-focus"
        else:
            command_type = "scene-transition"

    if target is None:
        keyword_targets = [
            ("battle-hud", "battle-hud"),
            ("battlefield-focus", "battle-hud"),
            ("tower", "tower-panel"),
            ("mana-upgrade", "mana-upgrade"),
            ("population-upgrade", "population-upgrade"),
            ("skill-window", "skill-window"),
            ("skill-menu", "skill-menu"),
            ("item-menu", "item-menu"),
            ("system-menu", "system-menu"),
            ("quest-panel", "quest-panel"),
            ("tutorial-subject", "tutorial-subject"),
            ("tutorial-anchor", "tutorial-anchor"),
            ("anchor", "tutorial-anchor"),
            ("guided-target", "guided-target"),
            ("guided-focus", "guided-focus"),
            ("dialogue-pose", "dialogue-pose"),
            ("impact", "impact-cue"),
            ("shock", "impact-cue"),
            ("tutorial-narration", "tutorial-narration"),
            ("banter-entry", "banter-entry"),
            ("scene-entry", "scene-entry"),
            ("scene-layout", "scene-layout"),
            ("scene-bridge", "scene-bridge"),
        ]
        for keyword, resolved_target in keyword_targets:
            if keyword in lowered_action:
                target = resolved_target
                break
        if target is None:
            if command_type == "presentation":
                target = "dialogue-pose"
            elif command_type == "emphasis":
                target = "impact-cue"
            elif command_type == "scene-layout":
                target = "scene-layout"
            elif command_type == "tutorial-mode":
                target = "tutorial-narration"
            elif command_type == "ui-focus":
                target = "scene-focus"
            else:
                target = "scene-transition"

    if command_id is None:
        command_id = label.lower().replace(" ", "-")

    return {
        "label": label,
        "action": action,
        "category": category,
        "confidence": confidence,
        "commandId": command_id,
        "commandType": command_type,
        "target": target,
    }


def auto_opcode_descriptor(
    mnemonic: str,
    profile: dict[str, Any],
    *,
    variant_key: str | None = None,
    args: list[Any] | None = None,
) -> dict[str, Any]:
    suffix = slugify_suffix(variant_key.split(":", 1)[1] if variant_key else mnemonic.replace("cmd-", ""))
    previous = first_counter_value(profile.get("previousCommands", []))
    following = first_counter_value(profile.get("nextCommands", []))
    args = args or []

    if mnemonic == "cmd-05":
        return build_scene_fields(
            label=f"dialogue-pose-{suffix}",
            action=f"apply-dialogue-pose-variant-{suffix}",
            category="presentation",
            confidence="medium",
            command_id=f"dialogue-pose-{suffix}",
            command_type="presentation",
            target="dialogue-pose",
        )
    if mnemonic == "cmd-08" and suffix != "40":
        return build_scene_fields(
            label=f"dialogue-pose-release-{suffix}",
            action=f"release-dialogue-pose-variant-{suffix}",
            category="presentation",
            confidence="medium",
            command_id=f"dialogue-pose-release-{suffix}",
            command_type="presentation",
            target="dialogue-pose",
        )
    if mnemonic == "cmd-00" and suffix != "0d":
        return build_scene_fields(
            label=f"battlefield-focus-preset-{suffix}",
            action=f"select-battlefield-focus-preset-{suffix}",
            category="ui-focus",
            confidence="medium",
            command_id=f"battlefield-focus-preset-{suffix}",
            command_type="ui-focus",
            target="battle-hud",
        )
    if mnemonic == "cmd-02":
        return build_scene_fields(
            label=f"tutorial-subject-preset-{suffix}",
            action=f"focus-tutorial-subject-preset-{suffix}",
            category="ui-focus",
            confidence="medium",
            command_id=f"tutorial-subject-preset-{suffix}",
            command_type="ui-focus",
            target="tutorial-subject",
        )
    if mnemonic == "cmd-06" and suffix != "0d":
        return build_scene_fields(
            label=f"guided-focus-preset-{suffix}",
            action=f"enter-guided-focus-preset-{suffix}",
            category="ui-focus",
            confidence="medium",
            command_id=f"guided-focus-preset-{suffix}",
            command_type="ui-focus",
            target="guided-focus",
        )
    if mnemonic == "cmd-0c" and suffix != "40":
        return build_scene_fields(
            label=f"guided-target-preset-{suffix}",
            action=f"bind-guided-target-preset-{suffix}",
            category="ui-focus",
            confidence="medium",
            command_id=f"guided-target-preset-{suffix}",
            command_type="ui-focus",
            target="guided-target",
        )
    if mnemonic == "cmd-0a" and suffix not in {"10", "40"}:
        return build_scene_fields(
            label=f"emphasis-start-{suffix}",
            action=f"start-emphasis-preset-{suffix}",
            category="emphasis",
            confidence="medium",
            command_id=f"emphasis-start-{suffix}",
            command_type="emphasis",
            target="impact-cue",
        )
    if mnemonic == "cmd-0b" and suffix not in {"10", "40"}:
        return build_scene_fields(
            label=f"emphasis-end-{suffix}",
            action=f"release-emphasis-preset-{suffix}",
            category="emphasis",
            confidence="medium",
            command_id=f"emphasis-end-{suffix}",
            command_type="emphasis",
            target="impact-cue",
        )

    if previous == "<start>" and following in {"set-left-portrait", "set-right-portrait", "set-expression", "cmd-05"}:
        return build_scene_fields(
            label=f"scene-layout-preset-{suffix}",
            action=f"load-scene-layout-preset-{suffix}",
            category="scene-bootstrap",
            confidence="medium",
            command_id=f"scene-layout-preset-{suffix}",
            command_type="scene-layout",
            target="scene-layout",
        )

    if previous in {"cmd-06", "cmd-0d", "cmd-20", "cmd-40", "cmd-42"} or following in {"cmd-00", "cmd-02", "cmd-06"}:
        return build_scene_fields(
            label=f"scene-bridge-preset-{suffix}",
            action=f"advance-scene-bridge-preset-{suffix}",
            category="scene-transition",
            confidence="low",
            command_id=f"scene-bridge-preset-{suffix}",
            command_type="scene-transition",
            target="scene-bridge",
        )

    if previous in {"set-left-portrait", "set-right-portrait", "set-expression"} or following in {"cmd-08", "<end>"}:
        return build_scene_fields(
            label=f"dialogue-pose-preset-{suffix}",
            action=f"apply-dialogue-pose-preset-{suffix}",
            category="presentation",
            confidence="low",
            command_id=f"dialogue-pose-preset-{suffix}",
            command_type="presentation",
            target="dialogue-pose",
        )

    return build_scene_fields(
        label=f"scene-transition-preset-{suffix}",
        action=f"apply-scene-transition-preset-{suffix}",
        category="scene-transition",
        confidence="low",
        command_id=f"scene-transition-preset-{suffix}",
        command_type="scene-transition",
        target="scene-transition",
    )


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
    variants: list[dict[str, Any]], mnemonic: str, profile: dict[str, Any]
) -> list[dict[str, Any]]:
    by_mnemonic = [item for item in variants if item.get("mnemonic") == mnemonic]
    curated: list[dict[str, Any]] = []
    for item in by_mnemonic:
        variant_key = str(item.get("variant"))
        override = OPCODE_VARIANT_OVERRIDES.get(variant_key)
        args = list(item.get("args", []))
        descriptor = (
            build_scene_fields(
                label=override["label"],
                action=override["action"],
                category=override["category"],
                confidence=override["confidence"],
            )
            if override is not None
            else auto_opcode_descriptor(mnemonic, profile, variant_key=variant_key, args=args)
        )
        if override is None:
            notes: list[str] = []
        else:
            notes = list(override.get("notes", []))
        curated.append(
            {
                "variant": variant_key,
                "args": args,
                **descriptor,
                "count": int(item.get("count", 0)),
                "evidenceSummary": [
                    variant_evidence_sentence(item),
                    *notes,
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
        variant_hints = build_variant_hints(variants, mnemonic, profile)
        descriptor = (
            build_scene_fields(
                label=override["label"],
                action=override["action"],
                category=override["category"],
                confidence=override["confidence"],
            )
            if override
            else auto_opcode_descriptor(mnemonic, profile)
        )
        evidence = [
            signal_sentence(profile),
            *override.get("notes", []),
        ]
        opcode_actions.append(
            {
                "mnemonic": mnemonic,
                **descriptor,
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
    unresolved_actions = [item for item in opcode_actions if str(item.get("action")) == "unknown-runtime-action"]
    findings = [
        "Opcode action export now assigns a stable scene-command id/type/target to every remaining non-dialogue opcode family.",
        "The strongest tutorial/UI variants still include cmd-00(0x0d), cmd-06(0x0d), and cmd-07/08/09/0a/0b/0c/0d/0e(0x40).",
        "All remaining low-frequency families now fall back to explicit scene-layout, scene-bridge, presentation, or transition preset names instead of unknown-runtime-action.",
    ]
    payload = {
        "summary": {
            "opcodeActionCount": len(opcode_actions),
            "featuredOpcodeCount": len(featured_actions),
            "curatedVariantCount": sum(len(item["variantHints"]) for item in opcode_actions),
            "unresolvedOpcodeCount": len(unresolved_actions),
        },
        "opcodeActions": opcode_actions,
        "featuredOpcodeActions": featured_actions,
        "findings": findings,
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
