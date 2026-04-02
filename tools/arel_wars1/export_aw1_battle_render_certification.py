#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TARGET_ARCHETYPES = [
    "dispatch",
    "tower-defense",
    "naturalhealing",
    "recall",
    "manawall",
    "armageddon",
    "managain",
    "special-stun",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AW1 representative battle/render equivalence certification report"
    )
    parser.add_argument("--side-by-side", type=Path, required=True, help="Path to AW1.side_by_side_report.json")
    parser.add_argument(
        "--stage-flow-certification",
        type=Path,
        required=True,
        help="Path to AW1.stage_flow_certification.json",
    )
    parser.add_argument(
        "--regression-certification",
        type=Path,
        required=True,
        help="Path to AW1.regression_stem_certification.json",
    )
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--render-pack", type=Path, required=True, help="Path to AW1.render_pack.json")
    parser.add_argument("--render-semantics", type=Path, required=True, help="Path to AW1.render_semantics.json")
    parser.add_argument("--candidate-suite", type=Path, required=True, help="Path to AW1.candidate_replay_suite.json")
    parser.add_argument("--reference-suite", type=Path, required=True, help="Path to AW1.golden_capture_suite.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to AW1.battle_render_certification.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(key)): item
        for item in items
        if isinstance(item, dict) and item.get(key) is not None
    }


def comparison_buckets(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        buckets.setdefault(str(record.get("category") or "unknown"), []).append(record)
    return buckets


def ratio_drift(candidate: float | int | None, reference: float | int | None) -> float | None:
    if candidate is None or reference is None:
        return None
    reference_value = abs(float(reference))
    if reference_value == 0:
        return 0.0 if abs(float(candidate)) == 0 else 1.0
    return abs(float(candidate) - float(reference)) / reference_value


def absolute_drift(candidate: float | int | None, reference: float | int | None) -> float | None:
    if candidate is None or reference is None:
        return None
    return abs(float(candidate) - float(reference))


def elapsed_tolerance(reference_elapsed_ms: int | float | None) -> float:
    if reference_elapsed_ms is None:
        return 5000.0
    return max(5000.0, abs(float(reference_elapsed_ms)) * 0.05)


def build_feature_set(stage_blueprint: dict[str, Any], route_label: str | None) -> set[str]:
    features: set[str] = set()
    if isinstance(route_label, str) and route_label:
        features.add(f"route:{route_label}")
    render_intent = stage_blueprint.get("renderIntent") or {}
    effect_intensity = render_intent.get("effectIntensity")
    if isinstance(effect_intensity, str) and effect_intensity:
        features.add(f"effect:{effect_intensity}")
    for archetype in stage_blueprint.get("recommendedArchetypeIds", []):
        if isinstance(archetype, str) and archetype in TARGET_ARCHETYPES:
            features.add(f"archetype:{archetype}")
    return features


def greedy_representative_selection(
    stage_blueprints: list[dict[str, Any]],
    stage_flow_by_family: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = []
    target_features = {
        "route:primary",
        "route:secondary",
        "effect:low",
        "effect:medium",
        "effect:high",
        *{f"archetype:{item}" for item in TARGET_ARCHETYPES},
    }
    for stage in stage_blueprints:
        family_id = stage.get("familyId")
        if family_id is None:
            continue
        stage_flow_stage = stage_flow_by_family.get(str(family_id), {})
        route_label = (
            stage.get("routeLabel")
            or stage_flow_stage.get("routeLabel")
        )
        features = build_feature_set(stage, route_label)
        if features:
            candidates.append((str(family_id), stage, features, route_label))

    uncovered = set(target_features)
    selected: list[dict[str, Any]] = []
    while uncovered:
        best: tuple[str, dict[str, Any], set[str], str | None] | None = None
        best_new_features: set[str] = set()
        for family_id, stage, features, route_label in candidates:
            newly_covered = features & uncovered
            if not newly_covered:
                continue
            if best is None:
                best = (family_id, stage, features, route_label)
                best_new_features = newly_covered
                continue
            if len(newly_covered) > len(best_new_features):
                best = (family_id, stage, features, route_label)
                best_new_features = newly_covered
                continue
            if len(newly_covered) == len(best_new_features) and family_id < best[0]:
                best = (family_id, stage, features, route_label)
                best_new_features = newly_covered
        if best is None:
            break
        family_id, stage, _, route_label = best
        selected.append(
            {
                "familyId": family_id,
                "title": stage.get("title"),
                "routeLabel": route_label,
                "effectIntensity": ((stage.get("renderIntent") or {}).get("effectIntensity")),
                "recommendedArchetypeIds": [
                    item for item in stage.get("recommendedArchetypeIds", []) if isinstance(item, str)
                ],
                "featuresCovered": sorted(best_new_features),
            }
        )
        uncovered -= best_new_features
        candidates = [item for item in candidates if item[0] != family_id]
    return selected


def classify_metric(
    *,
    name: str,
    candidate: Any,
    reference: Any,
    mismatch_class: str,
    tolerance: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if mismatch_class == "exact":
        matched = candidate == reference
    else:
        drift = absolute_drift(candidate, reference)
        matched = drift is not None and tolerance is not None and drift <= tolerance
    return {
        "field": name,
        "candidate": candidate,
        "reference": reference,
        "status": "match" if matched else "mismatch",
        "mismatchClass": mismatch_class,
        "tolerance": tolerance,
        "note": note,
    }


def build_battle_metrics(candidate: dict[str, Any], reference: dict[str, Any]) -> list[dict[str, Any]]:
    reference_elapsed = reference.get("elapsedMs")
    return [
        classify_metric(
            name="result",
            candidate=candidate.get("result"),
            reference=reference.get("result"),
            mismatch_class="exact",
            note="Battle outcome must match exactly for representative certification.",
        ),
        classify_metric(
            name="preferredMapIndex",
            candidate=candidate.get("preferredMapIndex"),
            reference=reference.get("preferredMapIndex"),
            mismatch_class="exact",
            note="Representative battle stages inherit exact stage/map binding from certified flow.",
        ),
        classify_metric(
            name="tempoBand",
            candidate=candidate.get("tempoBand"),
            reference=reference.get("tempoBand"),
            mismatch_class="exact",
            note="Tempo band should remain identical for the same route and stage script.",
        ),
        classify_metric(
            name="alliedWavesDispatched",
            candidate=candidate.get("alliedWavesDispatched"),
            reference=reference.get("alliedWavesDispatched"),
            mismatch_class="tolerant",
            tolerance=1.0,
            note="Wave counts may drift by at most one dispatch.",
        ),
        classify_metric(
            name="enemyWavesDispatched",
            candidate=candidate.get("enemyWavesDispatched"),
            reference=reference.get("enemyWavesDispatched"),
            mismatch_class="tolerant",
            tolerance=1.0,
            note="Wave counts may drift by at most one dispatch.",
        ),
        classify_metric(
            name="spawnCount",
            candidate=candidate.get("spawnCount"),
            reference=reference.get("spawnCount"),
            mismatch_class="tolerant",
            tolerance=max(1.0, abs(float(reference.get("spawnCount") or 0)) * 0.35),
            note="Spawn density may drift within the verification protocol 35% window.",
        ),
        classify_metric(
            name="projectileCount",
            candidate=candidate.get("projectileCount"),
            reference=reference.get("projectileCount"),
            mismatch_class="tolerant",
            tolerance=max(1.0, abs(float(reference.get("projectileCount") or 0)) * 0.35),
            note="Projectile density may drift within the verification protocol 35% window.",
        ),
        classify_metric(
            name="effectCount",
            candidate=candidate.get("effectCount"),
            reference=reference.get("effectCount"),
            mismatch_class="tolerant",
            tolerance=max(1.0, abs(float(reference.get("effectCount") or 0)) * 0.35),
            note="Effect density may drift within the verification protocol 35% window.",
        ),
        classify_metric(
            name="heroDeployCount",
            candidate=candidate.get("heroDeployCount"),
            reference=reference.get("heroDeployCount"),
            mismatch_class="tolerant",
            tolerance=max(1.0, abs(float(reference.get("heroDeployCount") or 0)) * 0.35),
            note="Hero deployment density may drift within the verification protocol 35% window.",
        ),
        classify_metric(
            name="alliedTowerMinHpRatio",
            candidate=candidate.get("alliedTowerMinHpRatio"),
            reference=reference.get("alliedTowerMinHpRatio"),
            mismatch_class="tolerant",
            tolerance=0.15,
            note="Tower HP trend may drift slightly while preserving battle equivalence.",
        ),
        classify_metric(
            name="enemyTowerMinHpRatio",
            candidate=candidate.get("enemyTowerMinHpRatio"),
            reference=reference.get("enemyTowerMinHpRatio"),
            mismatch_class="tolerant",
            tolerance=0.15,
            note="Tower HP trend may drift slightly while preserving battle equivalence.",
        ),
        classify_metric(
            name="elapsedMs",
            candidate=candidate.get("elapsedMs"),
            reference=reference.get("elapsedMs"),
            mismatch_class="tolerant",
            tolerance=elapsed_tolerance(reference_elapsed),
            note="Battle tempo may drift within a 5% or 5s window, whichever is larger.",
        ),
    ]


def collect_render_witnesses(
    representative_stages: list[dict[str, Any]],
    runtime_blueprint_by_family: dict[str, dict[str, Any]],
    render_pack: dict[str, Any],
    render_semantics: dict[str, Any],
    regression_certification: dict[str, Any],
) -> dict[str, Any]:
    stage_witnesses = []
    for stage in representative_stages:
        family_id = stage["familyId"]
        blueprint = runtime_blueprint_by_family.get(family_id, {})
        render_intent = blueprint.get("renderIntent") or {}
        stage_witnesses.append(
            {
                "familyId": family_id,
                "title": blueprint.get("title"),
                "routeLabel": blueprint.get("routeLabel"),
                "effectIntensity": render_intent.get("effectIntensity"),
                "bankRule": render_intent.get("bankRule"),
                "packedPixelHint": render_intent.get("packedPixelHint"),
                "recommendedArchetypeIds": blueprint.get("recommendedArchetypeIds", []),
            }
        )

    regression_stems = []
    for stem in regression_certification.get("stems", []):
        regression_stems.append(
            {
                "stem": stem.get("stem"),
                "verdict": stem.get("certificationVerdict"),
                "structuralMismatchCount": stem.get("structuralMismatchCount"),
                "heuristicWaiverCount": stem.get("heuristicWaiverCount"),
                "pzaTimingProof": ((stem.get("proofs") or {}).get("pzaBaseTiming")),
                "pzfFrameCompositionProof": ((stem.get("proofs") or {}).get("pzfFrameComposition")),
                "pzdImagePoolProof": ((stem.get("proofs") or {}).get("pzdImagePool")),
                "renderTransitionProof": ((stem.get("proofs") or {}).get("renderStateTransitions")),
            }
        )

    packed_specials = render_pack.get("packedPixelSpecials", [])
    return {
        "representativeStageRenderWitnesses": stage_witnesses,
        "nativeConfirmedBankSwitching": render_semantics.get("mplBankSwitching"),
        "packedPixel179": render_semantics.get("packedPixel179"),
        "ptcEmitterSemantics": render_semantics.get("ptcEmitterSemantics"),
        "effectEmitterAssignments": render_pack.get("effectEmitterAssignments"),
        "packedPixelSpecials": packed_specials,
        "regressionStemRenderProofs": regression_stems,
    }


def main() -> None:
    args = parse_args()
    side_by_side = read_json(args.side_by_side.resolve())
    stage_flow = read_json(args.stage_flow_certification.resolve())
    regression_certification = read_json(args.regression_certification.resolve())
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())
    render_pack = read_json(args.render_pack.resolve())
    render_semantics = read_json(args.render_semantics.resolve())
    candidate_suite = read_json(args.candidate_suite.resolve())
    reference_suite = read_json(args.reference_suite.resolve())

    stage_blueprints = [
        item for item in runtime_blueprint.get("stageBlueprints", []) if isinstance(item, dict)
    ]
    runtime_blueprint_by_family = by_key(stage_blueprints, "familyId")
    side_by_side_by_family = by_key(side_by_side.get("stageComparisons", []), "familyId")
    stage_flow_by_family = by_key(stage_flow.get("stages", []), "familyId")
    candidate_by_family = by_key(candidate_suite.get("completedTraces", []), "familyId")
    reference_by_family = by_key(reference_suite.get("completedTraces", []), "familyId")

    representative_stages = greedy_representative_selection(stage_blueprints, stage_flow_by_family)

    battle_stage_results = []
    exact_mismatch_count = 0
    tolerant_mismatch_count = 0
    covered_routes: set[str] = set()
    covered_effects: set[str] = set()
    covered_archetypes: set[str] = set()
    for stage in representative_stages:
        family_id = stage["familyId"]
        candidate_trace = candidate_by_family.get(family_id, {})
        reference_trace = reference_by_family.get(family_id, {})
        side_by_side_stage = side_by_side_by_family.get(family_id, {})
        stage_flow_stage = stage_flow_by_family.get(family_id, {})
        metrics = build_battle_metrics(candidate_trace, reference_trace)
        exact_mismatches = [metric for metric in metrics if metric["status"] == "mismatch" and metric["mismatchClass"] == "exact"]
        tolerant_mismatches = [metric for metric in metrics if metric["status"] == "mismatch" and metric["mismatchClass"] == "tolerant"]
        exact_mismatch_count += len(exact_mismatches)
        tolerant_mismatch_count += len(tolerant_mismatches)
        covered_routes.add(str(stage.get("routeLabel") or "unknown"))
        covered_effect = str(stage.get("effectIntensity") or "unknown")
        covered_effects.add(covered_effect)
        covered_archetypes.update(
            archetype
            for archetype in stage.get("recommendedArchetypeIds", [])
            if isinstance(archetype, str) and archetype in TARGET_ARCHETYPES
        )
        battle_stage_results.append(
            {
                **stage,
                "certificationVerdict": "certified" if not exact_mismatches and not tolerant_mismatches else "blocked",
                "metricCount": len(metrics),
                "exactMismatchCount": len(exact_mismatches),
                "tolerantMismatchCount": len(tolerant_mismatches),
                "battleMetrics": metrics,
                "structuralFlowVerdict": stage_flow_stage.get("certificationVerdict"),
                "sideBySideSummary": {
                    "status": side_by_side_stage.get("status"),
                    "mismatchCount": len(
                        [
                            item
                            for item in side_by_side_stage.get("comparisons", [])
                            if isinstance(item, dict) and item.get("status") == "mismatch"
                        ]
                    ),
                    "categoryBuckets": {
                        key: len(value)
                        for key, value in comparison_buckets(
                            [item for item in side_by_side_stage.get("comparisons", []) if isinstance(item, dict)]
                        ).items()
                    },
                },
            }
        )

    render_witnesses = collect_render_witnesses(
        battle_stage_results,
        runtime_blueprint_by_family,
        render_pack,
        render_semantics,
        regression_certification,
    )

    regression_summary = regression_certification.get("summary") or {}
    regression_render_blocked = int(regression_summary.get("blockedStemCount") or 0)
    native_render_mismatch_count = int(regression_summary.get("unresolvedStructuralMismatchCount") or 0)
    heuristic_render_waiver_count = int(regression_summary.get("heuristicWaiverCount") or 0)

    payload = {
        "specVersion": "aw1-battle-render-certification-v1",
        "generatedAtIso": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "summary": {
            "representativeBattleStageCount": len(battle_stage_results),
            "battleCertifiedCount": sum(1 for item in battle_stage_results if item["certificationVerdict"] == "certified"),
            "battleBlockedCount": sum(1 for item in battle_stage_results if item["certificationVerdict"] != "certified"),
            "representativeRenderStemCount": int(regression_summary.get("regressionStemCount") or 0),
            "renderCertifiedStemCount": int(regression_summary.get("certifiedStemCount") or 0),
            "renderBlockedStemCount": regression_render_blocked,
            "exactBattleMismatchCount": exact_mismatch_count,
            "tolerantBattleMismatchCount": tolerant_mismatch_count,
            "nativeRenderMismatchCount": native_render_mismatch_count,
            "heuristicRenderWaiverCount": heuristic_render_waiver_count,
            "routeCoverage": sorted(covered_routes),
            "effectIntensityCoverage": sorted(covered_effects),
            "archetypeCoverage": sorted(covered_archetypes),
        },
        "representativeSelectionRule": {
            "type": "greedy-coverage",
            "targetRoutes": ["primary", "secondary"],
            "targetEffectIntensities": ["high", "low", "medium"],
            "targetArchetypes": TARGET_ARCHETYPES,
            "notes": [
                "Pick the smallest representative stage set that covers both campaign routes, all three effect-intensity bands, and the core combat archetype set.",
                "The render representative set reuses the certified regression stems because those are the known render-divergence hotspots.",
            ],
        },
        "battleCertificationRule": {
            "blockingMismatchClasses": ["exact", "tolerant"],
            "exactFields": ["result", "preferredMapIndex", "tempoBand"],
            "tolerantFields": {
                "waveCounts": "<= 1 absolute drift",
                "spawnProjectileEffectHero": "<= 35% density drift",
                "towerHpRatios": "<= 0.15 absolute drift",
                "elapsedMs": "<= max(5000 ms, 5%)",
            },
        },
        "renderCertificationRule": {
            "blockingConditions": [
                "regression stem render certification blocked",
                "native-confirmed bank switching missing",
                "packed pixel 179 special missing",
            ],
            "heuristicWitnesses": [
                "PTC emitter semantics remain runtime-consistent heuristic and are visible as waivers, not blockers.",
            ],
        },
        "representativeBattleStages": battle_stage_results,
        "representativeRenderCoverage": render_witnesses,
        "findings": [
            "Representative battle certification widens equivalence beyond stage flow to density, timing, and tower-trend metrics on a coverage-driven stage set.",
            "Representative render certification combines the native-confirmed regression stems with route/effect-intensity stage witnesses.",
            "PTC emitter semantics remain visible as heuristic witnesses but do not block certification while native-confirmed render structure remains clean.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
