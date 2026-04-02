import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE4_PASS = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "desktop_spike" / "phase4-pass-session.json"
PHASE5_TRACE = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "desktop_spike" / "phase5-trace-session.json"
PHASE8_SESSION = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "differential_suite" / "phase8-session.json"
OUTPUT = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "go_no_go_gate" / "phase9-gate.json"
STAGE_BINDINGS_REL = "recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json"
GOLDEN_REL = "recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json"
TRACE_ID = "000-run-1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_show_json(rel_path: str) -> dict:
    result = subprocess.run(
        ["git", "show", f"origin/main:{rel_path}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def find_trace(data: dict, trace_id: str) -> dict:
    for trace in data.get("completedTraces", []):
        if trace.get("traceId") == trace_id:
            return trace
    raise KeyError(trace_id)


def find_stage_binding(data: dict, family_id: str) -> dict | None:
    for binding in data.get("stageBindings", []):
        if binding.get("familyId") == family_id:
            return binding
    return None


def scenario_by_name(session: dict, name: str) -> dict | None:
    for item in session.get("scenarioRuns", []):
        if item.get("name") == name:
            return item
    return None


def requirement(pass_value: bool, expected, actual, evidence: list[str], note: str | None = None) -> dict:
    result = {
        "pass": pass_value,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
    }
    if note:
        result["note"] = note
    return result


def main() -> int:
    phase4 = load_json(PHASE4_PASS)
    phase5 = load_json(PHASE5_TRACE)
    phase8 = load_json(PHASE8_SESSION)
    stage_bindings = git_show_json(STAGE_BINDINGS_REL)
    golden = git_show_json(GOLDEN_REL)
    golden_trace = find_trace(golden, TRACE_ID)
    binding = find_stage_binding(stage_bindings, golden_trace["familyId"])

    boot = scenario_by_name(phase8, "boot")
    battle_30s = scenario_by_name(phase8, "battle_30s")
    retreat = scenario_by_name(phase8, "retreat")
    orientation = scenario_by_name(phase8, "orientation")
    home_resume = scenario_by_name(phase8, "home_resume")

    desktop_checks = {
        "jniOnLoad": requirement(
            bool(phase4.get("sequence", [{}])[0].get("passed")),
            True,
            phase4.get("sequence", [{}])[0].get("passed"),
            [str(PHASE4_PASS)],
        ),
        "surfaceInit": requirement(
            bool(phase4.get("sequence", [{}, {}])[1].get("passed")),
            True,
            phase4.get("sequence", [{}, {}])[1].get("passed"),
            [str(PHASE4_PASS)],
        ),
        "firstRender": requirement(
            bool(phase5.get("firstRenderReached")) and bool(phase5.get("renderMarkerReached")),
            True,
            {
                "firstRenderReached": phase5.get("firstRenderReached"),
                "renderMarkerReached": phase5.get("renderMarkerReached"),
                "renderMarkerSymbol": phase5.get("renderMarkerSymbol"),
            },
            [str(PHASE5_TRACE)],
        ),
        "stable3Seconds": requirement(
            False,
            "3+ seconds stable execution evidence",
            None,
            [str(PHASE4_PASS), str(PHASE5_TRACE)],
            note="Current desktop spike sessions prove first render but do not record a 3-second steady-state render loop.",
        ),
    }

    expected_binding = {
        "familyId": golden_trace.get("familyId"),
        "aiIndex": binding.get("aiIndex") if binding else None,
        "preferredMapIndex": golden_trace.get("preferredMapIndex"),
    }

    in_app_checks = {
        "bootPath": requirement(
            bool(boot and boot.get("status")),
            ["boot", "title"],
            boot.get("observed", {}).get("scenePhaseSequence") if boot else None,
            [str(PHASE8_SESSION)],
        ),
        "familyAiPreferredMapMatch": requirement(
            False,
            expected_binding,
            {
                "familyId": phase8.get("referenceAlignment", {}).get("familyId"),
                "aiIndex": None,
                "preferredMapIndex": phase8.get("referenceAlignment", {}).get("preferredMapIndex"),
            },
            [str(PHASE8_SESSION), "git:origin/main:" + STAGE_BINDINGS_REL],
            note="Current in-app shim session does not yet expose actual runtime aiIndex/familyId/preferredMapIndex sourced from the running ARM path.",
        ),
        "scriptedBattleTraceMatch": requirement(
            False,
            {
                "sceneAt30s": "battle",
                "referenceResult": golden_trace.get("result"),
                "scenePhaseSequenceHead": golden_trace.get("scenePhaseSequence", [])[:2],
            },
            {
                "sceneAt30s": battle_30s.get("observed", {}).get("phaseAt30s") if battle_30s else None,
                "referenceResult": battle_30s.get("comparison", {}).get("referenceResult", {}).get("actual") if battle_30s else None,
                "battleScenarioStatus": battle_30s.get("status") if battle_30s else None,
            },
            [str(PHASE8_SESSION), "git:origin/main:" + GOLDEN_REL],
            note="At least one scripted battle trace must match. Current run reaches result before the 30-second oracle point.",
        ),
        "orientationLifecycle": requirement(
            bool(orientation and orientation.get("status")) and bool(home_resume and home_resume.get("status")),
            {"orientation": True, "homeResume": True},
            {
                "orientation": orientation.get("status") if orientation else None,
                "homeResume": home_resume.get("status") if home_resume else None,
            },
            [str(PHASE8_SESSION)],
        ),
        "retreatFlow": requirement(
            bool(retreat and retreat.get("status")),
            {"battleToResult": True, "resultType": "retreat"},
            retreat.get("observed") if retreat else None,
            [str(PHASE8_SESSION)],
        ),
    }

    all_checks = {**desktop_checks, **in_app_checks}
    failed = [name for name, check in all_checks.items() if not check["pass"]]
    verdict = "go" if not failed else "no-go"

    report = {
        "specVersion": "aw1-go-no-go-gate-v1",
        "generatedAtIso": now_iso(),
        "referenceTraceId": TRACE_ID,
        "referenceBinding": expected_binding,
        "desktopChecks": desktop_checks,
        "inAppChecks": in_app_checks,
        "verdict": verdict,
        "failedChecks": failed,
        "recommendedPath": (
            "continue in-app emulation"
            if verdict == "go"
            else "stop in-app emulation and switch to oracle-driven 1:1 porting"
        ),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)
    print(json.dumps({"verdict": verdict, "failedChecks": failed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
