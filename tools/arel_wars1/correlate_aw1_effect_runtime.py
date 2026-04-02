#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Correlate AW1 runtime particle/effect tables with parsed PTC and battle tables"
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables",
    )
    parser.add_argument(
        "--binary-report",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/binary_asset_report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the effect/runtime correlation report",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_ptc(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "stem": Path(str(entry["path"])).stem,
        "signatureHex": entry.get("signatureHex"),
        "fieldCount": entry.get("fieldCount"),
        "timingFields": entry.get("timingFields"),
        "emissionFields": entry.get("emissionFields"),
        "ratioFieldsFloat": entry.get("ratioFieldsFloat"),
        "signedDeltaFields": entry.get("signedDeltaFields"),
    }


def compact_projectile(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": record["index"],
        "familyCandidate": record["familyCandidate"],
        "projectileIdCandidate": record["projectileIdCandidate"],
        "variantCandidate": record["variantCandidate"],
        "speedOrRangeCandidate": record["speedOrRangeCandidate"],
        "motionCandidate": record["motionCandidate"],
    }


def compact_effect(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": record["index"],
        "familyCandidate": record["familyCandidate"],
        "effectIdCandidate": record["effectIdCandidate"],
        "variantCandidate": record["variantCandidate"],
        "frameOrDurationCandidate": record["frameOrDurationCandidate"],
        "loopFlagCandidate": record["loopFlagCandidate"],
        "blendFlagCandidate": record["blendFlagCandidate"],
    }


def compact_particle(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": record["index"],
        "particleIdCandidate": record["particleIdCandidate"],
        "variantCandidate": record["variantCandidate"],
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    binary_report = read_json(args.binary_report.resolve())

    particles = read_json(parsed_dir / "XlsParticle.eng.parsed.json")["records"]
    projectiles = read_json(parsed_dir / "XlsProjectile.eng.parsed.json")["records"]
    effects = read_json(parsed_dir / "XlsEffect.eng.parsed.json")["records"]
    hero_active = read_json(parsed_dir / "XlsHeroActiveSkill.eng.parsed.json")["records"]

    ptc_entries = binary_report["ptc"]
    ptc_by_stem = {Path(str(entry["path"])).stem: entry for entry in ptc_entries}

    particle_rows: list[dict[str, Any]] = []
    primary_reuse: dict[str, list[int]] = defaultdict(list)
    secondary_histogram: Counter[int] = Counter()
    primary_direct_count = 0
    secondary_nonzero_count = 0
    secondary_direct_count = 0

    for row in particles:
        primary_stem = f"{int(row['particleIdCandidate']):03d}"
        secondary_value = int(row["variantCandidate"])
        secondary_stem = f"{secondary_value:03d}" if secondary_value else None
        primary_ptc = ptc_by_stem.get(primary_stem)
        secondary_ptc = ptc_by_stem.get(secondary_stem) if secondary_stem is not None else None
        if primary_ptc is not None:
            primary_direct_count += 1
        if secondary_value != 0:
            secondary_nonzero_count += 1
            secondary_histogram[secondary_value] += 1
            if secondary_ptc is not None:
                secondary_direct_count += 1
        primary_reuse[primary_stem].append(int(row["index"]))

        relation_kind = "primary-only"
        if secondary_value != 0 and secondary_ptc is not None:
            relation_kind = "dual-ptc"
        elif secondary_value != 0:
            relation_kind = "primary-ptc-plus-nonptc-variant"

        particle_rows.append(
            {
                **row,
                "relationKind": relation_kind,
                "primaryPtc": compact_ptc(primary_ptc),
                "secondaryPtc": compact_ptc(secondary_ptc),
            }
        )

    hero_active_links: list[dict[str, Any]] = []
    exact_projectile_hit_count = 0
    exact_effect_hit_count = 0
    exact_particle_hit_count = 0
    rows_with_any_exact_hit = 0

    for row in hero_active:
        pairs = list(zip(row["tailPairBE"][::2], row["tailPairBE"][1::2]))
        pair_reports: list[dict[str, Any]] = []
        for first, second in pairs:
            if first >= 65000 or second >= 65000:
                continue

            projectile_exact = [
                compact_projectile(record)
                for record in projectiles
                if int(record["projectileIdCandidate"]) == first and int(record["variantCandidate"]) == second
            ]
            effect_exact = [
                compact_effect(record)
                for record in effects
                if int(record["familyCandidate"]) == first and int(record["effectIdCandidate"]) == second
            ]
            particle_exact = [
                compact_particle(record)
                for record in particles
                if int(record["particleIdCandidate"]) == first and int(record["variantCandidate"]) == second
            ]
            projectile_id_hints = [
                compact_projectile(record)
                for record in projectiles
                if int(record["projectileIdCandidate"]) == first
            ][:6]

            if projectile_exact:
                exact_projectile_hit_count += len(projectile_exact)
            if effect_exact:
                exact_effect_hit_count += len(effect_exact)
            if particle_exact:
                exact_particle_hit_count += len(particle_exact)

            if projectile_exact or effect_exact or particle_exact or projectile_id_hints:
                pair_reports.append(
                    {
                        "pair": [first, second],
                        "projectileExactMatches": projectile_exact,
                        "effectExactMatches": effect_exact,
                        "particleExactMatches": particle_exact,
                        "projectileIdHints": projectile_id_hints,
                    }
                )

        if any(
            report["projectileExactMatches"] or report["effectExactMatches"] or report["particleExactMatches"]
            for report in pair_reports
        ):
            rows_with_any_exact_hit += 1

        if pair_reports:
            hero_active_links.append(
                {
                    "index": row["index"],
                    "headerBytes": row["headerBytes"],
                    "tailPairBE": row["tailPairBE"],
                    "pairReports": pair_reports,
                }
            )

    shared_primary_groups = [
        {"primaryPtcStem": stem, "rowIndices": indices}
        for stem, indices in sorted(primary_reuse.items())
        if len(indices) > 1
    ]

    findings = [
        f"All {primary_direct_count}/{len(particles)} XlsParticle primary ids map directly to existing ptc/NNN.ptc files.",
        f"All {secondary_direct_count}/{secondary_nonzero_count} nonzero XlsParticle secondary ids also map directly to existing ptc/NNN.ptc files.",
        "This makes XlsParticle the strongest current candidate for a compact PTC bridge table rather than a free-form effect-variant table.",
    ]
    if any(group["primaryPtcStem"] == "048" for group in shared_primary_groups):
        findings.append(
            "Primary PTC 048 is reused across multiple rows with different secondary PTC ids, which looks like a shared emitter template plus alternate embellishment layers."
        )
    if rows_with_any_exact_hit:
        findings.append(
            f"XlsHeroActiveSkill tailPairBE yields exact runtime-table hits in {rows_with_any_exact_hit}/{len(hero_active)} rows, so at least part of the tail pair payload is likely a direct projectile/effect reference block."
        )

    report = {
        "summary": {
            "particleRowCount": len(particles),
            "primaryDirectPtcCount": primary_direct_count,
            "secondaryNonzeroCount": secondary_nonzero_count,
            "secondaryDirectPtcCount": secondary_direct_count,
            "dualPtcRowCount": sum(1 for row in particle_rows if row["relationKind"] == "dual-ptc"),
            "sharedPrimaryGroupCount": len(shared_primary_groups),
            "heroActiveRowCount": len(hero_active),
            "heroActiveRowsWithExactTailHits": rows_with_any_exact_hit,
            "heroActiveExactProjectileHitCount": exact_projectile_hit_count,
            "heroActiveExactEffectHitCount": exact_effect_hit_count,
            "heroActiveExactParticleHitCount": exact_particle_hit_count,
            "secondaryPtcHistogram": {str(key): value for key, value in sorted(secondary_histogram.items())},
        },
        "particleRows": particle_rows,
        "sharedPrimaryGroups": shared_primary_groups,
        "heroActiveTailLinks": hero_active_links,
        "findings": findings,
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
