#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AW1 original-vs-remake verification criteria and stage-by-stage checkpoints"
    )
    parser.add_argument(
        "--runtime-blueprint",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json",
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
        help="Path to write AW1.verification_spec.json",
    )
    parser.add_argument(
        "--web-output",
        type=Path,
        help="Optional path under public/ to copy the same json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def normalize_text(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join(tokens)


def dialogue_anchor_points(event_count: int) -> list[tuple[str, int]]:
    if event_count <= 0:
        return []
    candidates = [
        ("opening-1", 0),
        ("opening-2", 1),
        ("midpoint", event_count // 2),
        ("closing-1", max(event_count - 2, 0)),
        ("closing-2", event_count - 1),
    ]
    anchors: list[tuple[str, int]] = []
    seen_indices: set[int] = set()
    for anchor_id, index in candidates:
        if index < 0 or index >= event_count or index in seen_indices:
            continue
        seen_indices.add(index)
        anchors.append((anchor_id, index))
    return anchors


def build_dialogue_anchors(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for anchor_id, index in dialogue_anchor_points(len(events)):
        event = events[index]
        text = str(event.get("text") or "").strip()
        anchors.append(
            {
                "anchorId": anchor_id,
                "dialogueIndex": index,
                "speaker": event.get("speaker"),
                "text": text,
                "normalizedText": normalize_text(text),
                "tokenCount": len(normalize_text(text).split()) if text else 0,
            }
        )
    return anchors


def load_stage_events(script_root: Path, script_files: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for script_name in script_files:
        path = script_root / script_name
        if not path.exists():
            continue
        payload = read_json(path)
        if isinstance(payload, list):
            events.extend(item for item in payload if isinstance(item, dict))
    return events


def global_criteria() -> list[dict[str, Any]]:
    return [
        {
            "criterionId": "stage-binding-exact",
            "label": "Script family, AI row, and preferred map index must match exactly",
            "category": "binding",
            "matchMode": "exact",
            "threshold": None,
            "candidateSource": "AW1.stage_bindings.json / runtime trace",
            "referenceSource": "Legacy APK capture or instrumentation",
            "notes": [
                "familyId, aiIndex, routeLabel, and preferredMapIndex are hard-bound and should not drift.",
            ],
        },
        {
            "criterionId": "dialogue-count-exact",
            "label": "Dialogue event count must match the recovered script family exactly",
            "category": "story",
            "matchMode": "exact",
            "threshold": None,
            "candidateSource": "runtime trace",
            "referenceSource": "Legacy APK stage script capture",
            "notes": [
                "A stage run should reach every recovered dialogue event from opening line to closing line.",
            ],
        },
        {
            "criterionId": "dialogue-anchor-token-overlap",
            "label": "Opening, midpoint, and closing dialogue anchors should match by text tokens",
            "category": "story",
            "matchMode": "token-overlap",
            "threshold": 0.75,
            "candidateSource": "runtime trace dialogue anchors",
            "referenceSource": "Legacy APK transcript anchors",
            "notes": [
                "Token overlap allows minor punctuation or OCR differences while keeping stage identity strict.",
            ],
        },
        {
            "criterionId": "victory-phase-sequence",
            "label": "Victory flow must preserve deploy, battle, result, reward, unlock, and worldmap order",
            "category": "campaign",
            "matchMode": "sequence-exact",
            "threshold": None,
            "candidateSource": "runtime trace scenePhaseSequence",
            "referenceSource": "Legacy APK video or instrumentation",
            "notes": [
                "Unlock reveal is only required on stages that actually open a new node.",
            ],
        },
        {
            "criterionId": "defeat-phase-sequence",
            "label": "Defeat flow must preserve battle, result, and worldmap/retry order",
            "category": "campaign",
            "matchMode": "sequence-exact",
            "threshold": None,
            "candidateSource": "runtime trace scenePhaseSequence",
            "referenceSource": "Legacy APK video or instrumentation",
            "notes": [
                "Defeat should not silently skip back into battle without a result/worldmap handoff.",
            ],
        },
        {
            "criterionId": "objective-phase-sequence",
            "label": "Objective phase transitions must preserve the recovered order",
            "category": "battle",
            "matchMode": "sequence-exact",
            "threshold": None,
            "candidateSource": "runtime trace objectivePhaseSequence",
            "referenceSource": "Legacy APK battle observation",
            "notes": [
                "This check compares the ordered unique objective phases, not every repeated tick update.",
            ],
        },
        {
            "criterionId": "wave-count-tolerance",
            "label": "Allied and enemy wave counts must stay within one wave of the reference",
            "category": "battle",
            "matchMode": "tolerance",
            "threshold": 1,
            "candidateSource": "runtime trace wave counts",
            "referenceSource": "Legacy APK wave capture",
            "notes": [
                "Wave pacing can drift slightly during reconstruction, but whole-wave mismatches should stay bounded.",
            ],
        },
        {
            "criterionId": "battle-metric-tolerance",
            "label": "Spawn, projectile, and effect totals should stay within 35% of the reference",
            "category": "battle",
            "matchMode": "tolerance",
            "threshold": 0.35,
            "candidateSource": "runtime trace battle metrics",
            "referenceSource": "Legacy APK captured metrics",
            "notes": [
                "This is a tolerance gate for reconstructed simulation density rather than an exact count gate.",
            ],
        },
        {
            "criterionId": "render-rule-exact",
            "label": "Recovered render rule labels must match the stage render intent exactly",
            "category": "render",
            "matchMode": "exact",
            "threshold": None,
            "candidateSource": "runtime trace / runtime blueprint",
            "referenceSource": "Native reverse-engineering notes + visual capture",
            "notes": [
                "Checks effect intensity, MPL bank rule label, and any packed-pixel special handling attached to the stage.",
            ],
        },
        {
            "criterionId": "result-and-unlock-exact",
            "label": "Stage outcome and unlock target must match the reference result path exactly",
            "category": "campaign",
            "matchMode": "exact",
            "threshold": None,
            "candidateSource": "runtime trace result + unlock label",
            "referenceSource": "Legacy APK campaign capture",
            "notes": [
                "The comparison should confirm both the outcome and the next unlocked route when a clear occurs.",
            ],
        },
    ]


def build_stage_check(stage_index: int, stage: dict[str, Any], script_root: Path, total_stage_count: int) -> dict[str, Any]:
    script_files = list(stage.get("scriptFiles", []))
    events = load_stage_events(script_root, script_files)
    anchors = build_dialogue_anchors(events)
    map_binding = stage.get("mapBinding") if isinstance(stage.get("mapBinding"), dict) else {}
    render_intent = stage.get("renderIntent") if isinstance(stage.get("renderIntent"), dict) else {}
    title = stage.get("title")
    route_label = str(map_binding.get("storyBranch", "primary"))
    unlock_index = stage_index + 1 if stage_index + 1 < total_stage_count else None
    victory_sequence = ["deploy-briefing", "battle", "result-hold", "reward-review"]
    if unlock_index is not None:
        victory_sequence.append("unlock-reveal")
    victory_sequence.append("worldmap")

    comparison_checks = [
        {
            "criterionId": "stage-binding-exact",
            "expectedValue": {
                "familyId": stage.get("familyId"),
                "aiIndex": stage.get("aiIndex"),
                "routeLabel": route_label,
                "preferredMapIndex": map_binding.get("preferredMapIndex"),
            },
        },
        {
            "criterionId": "dialogue-count-exact",
            "expectedValue": len(events),
        },
        {
            "criterionId": "dialogue-anchor-token-overlap",
            "expectedValue": len(anchors),
        },
        {
            "criterionId": "victory-phase-sequence",
            "expectedValue": victory_sequence,
        },
        {
            "criterionId": "defeat-phase-sequence",
            "expectedValue": ["battle", "result-hold", "worldmap"],
        },
        {
            "criterionId": "objective-phase-sequence",
            "expectedValue": stage.get("renderIntent", {}).get("effectIntensity", "medium"),
            "notes": [
                "Use the runtime objective trace together with total waves and favored lane when comparing the legacy APK.",
            ],
        },
        {
            "criterionId": "wave-count-tolerance",
            "expectedValue": max(3, round(len(events) / 24) + max(round((stage.get("runtimeFields") or {}).get("tierCandidate", 10) / 20), 1)),
        },
        {
            "criterionId": "render-rule-exact",
            "expectedValue": {
                "effectIntensity": render_intent.get("effectIntensity"),
                "bankRule": render_intent.get("bankRule"),
                "packedPixelHint": render_intent.get("packedPixelHint"),
            },
        },
        {
            "criterionId": "result-and-unlock-exact",
            "expectedValue": {
                "rewardText": stage.get("rewardText"),
                "nextUnlockNodeIndex": unlock_index + 1 if unlock_index is not None else None,
            },
        },
    ]

    return {
        "stageIndex": stage_index + 1,
        "familyId": stage.get("familyId"),
        "title": title,
        "aiIndex": stage.get("aiIndex"),
        "routeLabel": route_label,
        "preferredMapIndex": map_binding.get("preferredMapIndex"),
        "templateGroupId": map_binding.get("templateGroupId"),
        "scriptFiles": script_files,
        "scriptEventCount": len(events),
        "rewardText": stage.get("rewardText"),
        "hintText": stage.get("hintText"),
        "topSpeakers": [str(item[0]) for item in list(stage.get("topSpeakers", []))[:4] if isinstance(item, list) and item],
        "recommendedArchetypes": list(stage.get("recommendedArchetypeIds", [])),
        "effectIntensity": render_intent.get("effectIntensity"),
        "bankRule": render_intent.get("bankRule"),
        "tutorialCueCount": len(stage.get("tutorialChainCues", [])),
        "opcodeCueCount": len(stage.get("opcodeCues", [])),
        "dialogueAnchors": anchors,
        "expectedVictoryPhaseSequence": victory_sequence,
        "expectedDefeatPhaseSequence": ["battle", "result-hold", "worldmap"],
        "comparisonChecks": comparison_checks,
    }


def main() -> None:
    args = parse_args()
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())
    script_root = args.script_root.resolve()
    stage_blueprints = list(runtime_blueprint.get("stageBlueprints", []))
    criteria = global_criteria()
    stage_checks = [
        build_stage_check(index, stage, script_root, len(stage_blueprints))
        for index, stage in enumerate(stage_blueprints)
        if isinstance(stage, dict)
    ]

    payload = {
        "summary": {
            "stageCount": len(stage_checks),
            "globalCriterionCount": len(criteria),
            "exactCriterionCount": sum(1 for item in criteria if item["matchMode"] == "exact"),
            "tolerantCriterionCount": sum(1 for item in criteria if item["matchMode"] != "exact"),
            "dialogueAnchorCount": sum(len(item["dialogueAnchors"]) for item in stage_checks),
        },
        "globalCriteria": criteria,
        "stageChecks": stage_checks,
        "captureProtocol": {
            "referenceTraceShape": [
                "familyId",
                "routeLabel",
                "preferredMapIndex",
                "dialogueEventsSeen",
                "dialogueAnchorsSeen[]",
                "scenePhaseSequence[]",
                "objectivePhaseSequence[]",
                "enemyWavesDispatched",
                "alliedWavesDispatched",
                "spawnCount",
                "projectileCount",
                "effectCount",
                "heroDeployCount",
                "result",
                "resultReason",
                "unlockRevealLabel",
            ],
            "checklist": [
                "Capture one victory trace and one defeat trace for every stage family that can branch into both outcomes.",
                "Record opening, midpoint, and closing dialogue anchors exactly as they appear in the legacy APK.",
                "Capture worldmap, deploy, battle, result, reward, and unlock transitions in order rather than comparing isolated screenshots.",
                "Treat map binding, route label, dialogue count, and unlock target as exact gates before any tolerant battle metrics are considered.",
            ],
        },
        "findings": [
            "Verification is stage-family based and uses the hard script-family/XlsAi/map-bin binding path as its identity anchor.",
            "The comparison spec separates exact story/campaign checks from tolerant battle-density checks so visual/runtime drift can be measured without hiding structural mismatches.",
            "This spec is intended to be paired with runtime trace exports from the reconstructed engine and manually captured reference traces from the legacy APK.",
        ],
    }

    output_path = args.output.resolve()
    write_json(output_path, payload)
    if args.web_output:
      write_json(args.web_output.resolve(), payload)


if __name__ == "__main__":
    main()
