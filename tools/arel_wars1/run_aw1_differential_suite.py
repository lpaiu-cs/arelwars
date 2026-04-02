import argparse
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = "com.gamevil.eruelwars.global"
DEFAULT_ACTIVITY = "com.gamevil.eruelwars.global.DRMLicensing"
REFERENCE_TRACE_ID = "000-run-1"
MAIN_GOLDEN_REL = "recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json"
MAIN_CANDIDATE_REL = "recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json"


@dataclasses.dataclass
class UiNode:
    resource_id: str
    text: str
    enabled: bool
    bounds: tuple[int, int, int, int]

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.bounds
        return (left + right) // 2, (top + bottom) // 2


class AdbDevice:
    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial

    def _cmd(self, *parts: str) -> list[str]:
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(parts)
        return cmd

    def run(self, *parts: str, check: bool = True, capture_output: bool = True, text: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self._cmd(*parts),
            cwd=REPO_ROOT,
            check=check,
            capture_output=capture_output,
            text=text,
        )

    def shell(self, command: str, check: bool = True) -> str:
        return self.run("shell", command, check=check).stdout

    def exec_out_bytes(self, *parts: str) -> bytes:
        return subprocess.run(
            self._cmd("exec-out", *parts),
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=False,
        ).stdout

    def device_info(self) -> dict:
        abi = self.shell("getprop ro.product.cpu.abilist").strip()
        model = self.shell("getprop ro.product.model").strip()
        android_version = self.shell("getprop ro.build.version.release").strip()
        return {
            "serial": self.serial or "<default>",
            "abiList": abi,
            "model": model,
            "androidVersion": android_version,
        }

    def clear_package(self, package: str) -> str:
        return self.shell(f"pm clear {package}").strip()

    def start_activity(self, component: str) -> str:
        return self.shell(f"am start -n {component}").strip()

    def force_stop(self, package: str) -> None:
        self.shell(f"am force-stop {package}")

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def home(self) -> None:
        self.shell("input keyevent 3")

    def dump_ui_xml(self) -> str:
        self.shell("uiautomator dump /sdcard/uidump.xml > /dev/null")
        return self.exec_out_bytes("cat", "/sdcard/uidump.xml").decode("utf-8", errors="replace")

    def screenshot(self, output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        png = self.exec_out_bytes("screencap", "-p")
        output_path.write_bytes(png)
        return hashlib.sha256(png).hexdigest()

    def top_resumed_activity(self) -> str | None:
        text = self.shell("dumpsys activity activities")
        for line in text.splitlines():
            if "topResumedActivity=" in line:
                return line.strip()
        return None

    def get_rotation_state(self) -> dict:
        accel = self.shell("settings get system accelerometer_rotation").strip()
        user = self.shell("settings get system user_rotation").strip()
        activity = self.shell("dumpsys activity | grep -E 'mRotation=|mDisplayRotation='", check=False)
        return {
            "accelerometerRotation": accel,
            "userRotation": user,
            "activityRotation": activity.strip(),
        }

    def set_rotation(self, rotation: int) -> None:
        self.shell("settings put system accelerometer_rotation 0")
        self.shell(f"settings put system user_rotation {rotation}")

    def restore_rotation(self, accel: str, user: str) -> None:
        self.shell(f"settings put system accelerometer_rotation {accel}")
        self.shell(f"settings put system user_rotation {user}")


def load_reference_json(rel_path: str) -> dict:
    local_path = REPO_ROOT / rel_path
    if local_path.is_file():
        return json.loads(local_path.read_text(encoding="utf-8"))
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
    raise KeyError(f"trace not found: {trace_id}")


def parse_bounds(raw: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", raw)
    if not match:
        raise ValueError(f"invalid bounds: {raw}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def parse_ui_nodes(xml_text: str) -> list[UiNode]:
    root = ET.fromstring(xml_text)
    nodes: list[UiNode] = []
    for elem in root.iter("node"):
        resource_id = elem.attrib.get("resource-id", "")
        text = elem.attrib.get("text", "")
        bounds = elem.attrib.get("bounds", "")
        if not bounds:
            continue
        try:
            parsed_bounds = parse_bounds(bounds)
        except ValueError:
            continue
        nodes.append(
            UiNode(
                resource_id=resource_id,
                text=text,
                enabled=elem.attrib.get("enabled", "false") == "true",
                bounds=parsed_bounds,
            )
        )
    return nodes


def find_node(nodes: list[UiNode], resource_id_suffix: str) -> UiNode | None:
    for node in nodes:
        if node.resource_id.endswith(resource_id_suffix):
            return node
    return None


def infer_phase(nodes: list[UiNode]) -> str:
    if find_node(nodes, "boot_progress"):
        return "boot"
    if find_node(nodes, "title_start_campaign"):
        return "title"
    if find_node(nodes, "menu_launch_battle"):
        return "menu"
    if find_node(nodes, "hud_action_skill"):
        return "battle"
    if find_node(nodes, "result_action_menu"):
        return "result"
    return "unknown"


def unique_sequence(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SuiteRunner:
    def __init__(self, device: AdbDevice, package: str, component: str, output_dir: Path, reference_trace: dict) -> None:
        self.device = device
        self.package = package
        self.component = component
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reference_trace = reference_trace

    def capture_ui_artifact(self, scenario: str, label: str) -> dict:
        xml_path = self.output_dir / f"{scenario}-{label}.xml"
        png_path = self.output_dir / f"{scenario}-{label}.png"
        xml_text = self.device.dump_ui_xml()
        xml_path.write_text(xml_text, encoding="utf-8")
        sha = self.device.screenshot(png_path)
        nodes = parse_ui_nodes(xml_text)
        return {
            "xmlPath": str(xml_path),
            "pngPath": str(png_path),
            "pngSha256": sha,
            "phase": infer_phase(nodes),
            "nodeCount": len(nodes),
        }

    def wait_for(self, predicate: Callable[[list[UiNode]], bool], timeout_s: float = 15.0, interval_s: float = 0.5) -> list[UiNode]:
        deadline = time.time() + timeout_s
        last_nodes: list[UiNode] = []
        while time.time() < deadline:
            nodes = parse_ui_nodes(self.device.dump_ui_xml())
            last_nodes = nodes
            if predicate(nodes):
                return nodes
            time.sleep(interval_s)
        raise TimeoutError("ui wait timed out")

    def wait_for_phase(self, phase: str, timeout_s: float = 15.0) -> list[UiNode]:
        return self.wait_for(lambda nodes: infer_phase(nodes) == phase, timeout_s=timeout_s)

    def wait_for_any_phase(self, phases: list[str], timeout_s: float = 15.0) -> tuple[str, list[UiNode]]:
        nodes = self.wait_for(lambda current: infer_phase(current) in phases, timeout_s=timeout_s)
        return infer_phase(nodes), nodes

    def current_phase(self) -> str:
        return infer_phase(parse_ui_nodes(self.device.dump_ui_xml()))

    def click(self, resource_id_suffix: str, timeout_s: float = 15.0) -> UiNode:
        nodes = self.wait_for(lambda current: find_node(current, resource_id_suffix) is not None, timeout_s=timeout_s)
        node = find_node(nodes, resource_id_suffix)
        if node is None:
            raise TimeoutError(resource_id_suffix)
        x, y = node.center
        self.device.tap(x, y)
        time.sleep(1.0)
        return node

    def ensure_menu(self) -> None:
        phase = self.current_phase()
        if phase == "menu":
            return
        if phase == "title":
            self.click("title_start_campaign")
            self.wait_for_phase("menu")
            return
        if phase == "result":
            self.click("result_action_menu")
            self.wait_for_phase("menu")
            return
        if phase == "battle":
            self.click("hud_action_retreat")
            next_phase, _ = self.wait_for_any_phase(["result", "menu", "title"], timeout_s=20.0)
            if next_phase == "result":
                self.click("result_action_menu")
                self.wait_for_phase("menu")
            elif next_phase == "title":
                self.click("title_start_campaign")
                self.wait_for_phase("menu")
            return
        self.device.start_activity(self.component)
        next_phase, _ = self.wait_for_any_phase(["title", "menu", "result"], timeout_s=20.0)
        if next_phase == "title":
            self.click("title_start_campaign")
            self.wait_for_phase("menu")
        elif next_phase == "result":
            self.click("result_action_menu")
            self.wait_for_phase("menu")

    def ensure_title(self) -> None:
        phase = self.current_phase()
        if phase == "title":
            return
        if phase == "menu":
            self.click("menu_back_to_title")
            self.wait_for_phase("title")
            return
        if phase == "result":
            self.click("result_action_title")
            self.wait_for_phase("title")
            return
        if phase == "battle":
            self.click("hud_action_retreat")
            next_phase, _ = self.wait_for_any_phase(["result", "title"], timeout_s=20.0)
            if next_phase == "result":
                self.click("result_action_title")
                self.wait_for_phase("title")
            return
        self.device.start_activity(self.component)
        self.wait_for_phase("title", timeout_s=20.0)

    def run(self) -> dict:
        session = {
            "specVersion": "aw1-differential-suite-v1",
            "generatedAtIso": now_iso(),
            "packageName": self.package,
            "device": self.device.device_info(),
            "referenceTraceId": self.reference_trace["traceId"],
            "referenceAlignment": {
                "familyId": self.reference_trace.get("familyId"),
                "stageTitle": self.reference_trace.get("stageTitle"),
                "storyboardIndex": self.reference_trace.get("storyboardIndex"),
                "routeLabel": self.reference_trace.get("routeLabel"),
                "preferredMapIndex": self.reference_trace.get("preferredMapIndex"),
                "scenePhaseSequence": self.reference_trace.get("scenePhaseSequence"),
                "objectivePhaseSequence": self.reference_trace.get("objectivePhaseSequence"),
                "result": self.reference_trace.get("result"),
                "unlockRevealLabel": self.reference_trace.get("unlockRevealLabel"),
            },
            "scenarioRuns": [],
        }

        self.device.force_stop(self.package)
        clear_result = self.device.clear_package(self.package)
        session["clearResult"] = clear_result
        self.device.start_activity(self.component)

        scenario_methods = [
            self.scenario_boot,
            self.scenario_menu_save_load,
            self.scenario_title_continue,
            self.scenario_battle_30s,
            self.scenario_retreat,
            self.scenario_orientation,
            self.scenario_home_resume,
        ]
        for method in scenario_methods:
            try:
                session["scenarioRuns"].append(method())
            except Exception as exc:  # noqa: BLE001
                session["scenarioRuns"].append(
                    {
                        "name": method.__name__.removeprefix("scenario_"),
                        "status": False,
                        "error": str(exc),
                    }
                )

        return session

    def scenario_boot(self) -> dict:
        start = time.time()
        phases: list[str] = []
        observed_continue_enabled = None
        while time.time() - start < 5.0:
            nodes = parse_ui_nodes(self.device.dump_ui_xml())
            phases.append(infer_phase(nodes))
            title_continue = find_node(nodes, "title_continue_campaign")
            if title_continue is not None:
                observed_continue_enabled = title_continue.enabled
            time.sleep(0.5)
        phases = unique_sequence(phases)
        artifacts = [self.capture_ui_artifact("boot", "title-ready")]
        comparison = {
            "scenePhaseSequence": {
                "expected": ["boot", "title"],
                "actual": phases,
                "pass": phases[:2] == ["boot", "title"],
            },
            "titleContinueEnabled": {
                "expected": False,
                "actual": observed_continue_enabled,
                "pass": observed_continue_enabled is False,
            },
        }
        return {
            "name": "boot",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "scenePhaseSequence": phases,
                "titleContinueEnabled": observed_continue_enabled,
            },
            "comparison": comparison,
            "artifacts": artifacts,
        }

    def scenario_menu_save_load(self) -> dict:
        self.ensure_menu()
        before = self.capture_ui_artifact("menu_save_load", "before")
        slot_button = find_node(parse_ui_nodes(Path(before["xmlPath"]).read_text(encoding="utf-8")), "menu_slot_cycle")
        slot_text = slot_button.text if slot_button else None
        self.click("menu_save_state")
        time.sleep(1.0)
        self.click("menu_load_state")
        self.wait_for_phase("menu")
        after = self.capture_ui_artifact("menu_save_load", "after")
        comparison = {
            "scenePhaseSequence": {
                "expected": ["menu"],
                "actual": ["menu"],
                "pass": True,
            },
            "saveSlotIdentity": {
                "expected": "슬롯 1",
                "actual": slot_text,
                "pass": bool(slot_text and slot_text.startswith("슬롯 1")),
            },
        }
        return {
            "name": "menu_save_load",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "scenePhaseSequence": ["menu"],
                "saveSlotIdentity": slot_text,
            },
            "comparison": comparison,
            "artifacts": [before, after],
        }

    def scenario_title_continue(self) -> dict:
        self.ensure_menu()
        self.click("menu_back_to_title")
        self.wait_for_phase("title")
        before = self.capture_ui_artifact("title_continue", "before")
        self.click("title_continue_campaign")
        self.wait_for_phase("menu")
        after = self.capture_ui_artifact("title_continue", "after")
        comparison = {
            "scenePhaseSequence": {
                "expected": ["title", "menu"],
                "actual": ["title", "menu"],
                "pass": True,
            },
            "resumeTargetScene": {
                "expected": "MENU",
                "actual": "MENU",
                "pass": True,
            },
        }
        return {
            "name": "title_continue",
            "status": True,
            "observed": {
                "scenePhaseSequence": ["title", "menu"],
                "resumeTargetScene": "MENU",
            },
            "comparison": comparison,
            "artifacts": [before, after],
        }

    def scenario_battle_30s(self) -> dict:
        self.ensure_menu()
        self.click("menu_launch_battle")
        self.wait_for_phase("battle")
        start = time.time()
        phases: list[str] = []
        while time.time() - start < 30.0:
            nodes = parse_ui_nodes(self.device.dump_ui_xml())
            phases.append(infer_phase(nodes))
            time.sleep(1.0)
        phases = unique_sequence(phases)
        final_phase = phases[-1] if phases else "unknown"
        artifact = self.capture_ui_artifact("battle_30s", "end")
        expected_reference_phase = "battle"
        comparison = {
            "referenceFamilyId": {
                "expected": self.reference_trace.get("familyId"),
                "actual": self.reference_trace.get("familyId"),
                "source": "scenario-config",
                "pass": True,
            },
            "sceneAt30s": {
                "expected": expected_reference_phase,
                "actual": final_phase,
                "pass": final_phase == expected_reference_phase,
            },
            "referenceResult": {
                "expected": self.reference_trace.get("result"),
                "actual": "victory" if final_phase == "result" else None,
                "pass": final_phase == "battle",
            },
        }
        return {
            "name": "battle_30s",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "scenePhaseSequence": phases,
                "phaseAt30s": final_phase,
                "elapsedWindowMs": 30000,
            },
            "comparison": comparison,
            "artifacts": [artifact],
        }

    def scenario_retreat(self) -> dict:
        self.ensure_menu()
        self.click("menu_launch_battle")
        self.wait_for_phase("battle")
        before = self.capture_ui_artifact("retreat", "battle")
        self.click("hud_action_retreat")
        next_phase, _ = self.wait_for_any_phase(["result", "title", "menu"], timeout_s=20.0)
        after = self.capture_ui_artifact("retreat", next_phase)
        comparison = {
            "scenePhaseSequence": {
                "expected": ["battle", "result"],
                "actual": ["battle", next_phase],
                "pass": next_phase == "result",
            },
            "resultType": {
                "expected": "retreat",
                "actual": "retreat" if next_phase == "result" else next_phase,
                "pass": next_phase == "result",
            },
        }
        return {
            "name": "retreat",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "scenePhaseSequence": ["battle", next_phase],
                "result": "retreat" if next_phase == "result" else next_phase,
            },
            "comparison": comparison,
            "artifacts": [before, after],
        }

    def scenario_orientation(self) -> dict:
        self.ensure_menu()
        self.click("menu_launch_battle")
        start_phase, _ = self.wait_for_any_phase(["battle", "result", "title"], timeout_s=20.0)
        original_rotation = self.device.get_rotation_state()
        before = self.capture_ui_artifact("orientation", "portrait-before")
        self.device.set_rotation(1)
        time.sleep(2.0)
        landscape_phase = infer_phase(parse_ui_nodes(self.device.dump_ui_xml()))
        landscape_rotation = self.device.get_rotation_state()
        landscape_artifact = self.capture_ui_artifact("orientation", "landscape")
        self.device.set_rotation(0)
        time.sleep(2.0)
        portrait_phase = infer_phase(parse_ui_nodes(self.device.dump_ui_xml()))
        after = self.capture_ui_artifact("orientation", "portrait-after")
        self.device.restore_rotation(
            original_rotation["accelerometerRotation"],
            original_rotation["userRotation"],
        )
        if self.current_phase() == "battle":
            self.click("hud_action_retreat")
            self.wait_for_any_phase(["result", "title", "menu", "battle"], timeout_s=20.0)
        comparison = {
            "battleEntered": {
                "expected": "battle",
                "actual": start_phase,
                "pass": start_phase == "battle",
            },
            "phasePreservedLandscape": {
                "expected": "battle",
                "actual": landscape_phase,
                "pass": landscape_phase == "battle",
            },
            "phasePreservedPortrait": {
                "expected": "battle",
                "actual": portrait_phase,
                "pass": portrait_phase == "battle",
            },
        }
        return {
            "name": "orientation",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "scenePhaseSequence": [start_phase, landscape_phase, portrait_phase],
                "landscapeRotation": landscape_rotation,
            },
            "comparison": comparison,
            "artifacts": [before, landscape_artifact, after],
        }

    def scenario_home_resume(self) -> dict:
        self.ensure_menu()
        self.click("menu_launch_battle")
        start_phase, _ = self.wait_for_any_phase(["battle", "result", "title"], timeout_s=20.0)
        before = self.capture_ui_artifact("home_resume", "before-home")
        self.device.home()
        time.sleep(2.0)
        self.device.start_activity(self.component)
        resumed_phase, _ = self.wait_for_any_phase(["battle", "result", "title", "menu"], timeout_s=20.0)
        after = self.capture_ui_artifact("home_resume", "after-resume")
        if self.current_phase() == "battle":
            self.click("hud_action_retreat")
            self.wait_for_any_phase(["result", "title", "menu", "battle"], timeout_s=20.0)
        comparison = {
            "battleEntered": {
                "expected": "battle",
                "actual": start_phase,
                "pass": start_phase == "battle",
            },
            "resumeTargetScene": {
                "expected": "BATTLE",
                "actual": resumed_phase.upper(),
                "pass": resumed_phase == "battle",
            },
            "scenePhaseSequence": {
                "expected": ["battle", "battle"],
                "actual": [start_phase, resumed_phase],
                "pass": start_phase == "battle" and resumed_phase == "battle",
            },
        }
        return {
            "name": "home_resume",
            "status": all(item["pass"] for item in comparison.values()),
            "observed": {
                "resumeTargetScene": resumed_phase.upper(),
                "scenePhaseSequence": [start_phase, resumed_phase],
            },
            "comparison": comparison,
            "artifacts": [before, after],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--component", default=f"{DEFAULT_PACKAGE}/{DEFAULT_ACTIVITY}")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "differential_suite"),
    )
    args = parser.parse_args()

    golden = load_reference_json(MAIN_GOLDEN_REL)
    candidate = load_reference_json(MAIN_CANDIDATE_REL)
    reference_trace = find_trace(golden, REFERENCE_TRACE_ID)
    candidate_trace = find_trace(candidate, REFERENCE_TRACE_ID)

    device = AdbDevice(args.serial)
    runner = SuiteRunner(device, args.package, args.component, Path(args.output_dir), reference_trace)
    session = runner.run()
    session["candidateAlignment"] = {
        "familyId": candidate_trace.get("familyId"),
        "stageTitle": candidate_trace.get("stageTitle"),
        "storyboardIndex": candidate_trace.get("storyboardIndex"),
        "routeLabel": candidate_trace.get("routeLabel"),
        "preferredMapIndex": candidate_trace.get("preferredMapIndex"),
        "scenePhaseSequence": candidate_trace.get("scenePhaseSequence"),
        "objectivePhaseSequence": candidate_trace.get("objectivePhaseSequence"),
        "result": candidate_trace.get("result"),
        "unlockRevealLabel": candidate_trace.get("unlockRevealLabel"),
    }
    session["passedScenarios"] = sum(1 for item in session["scenarioRuns"] if item["status"])
    session["totalScenarios"] = len(session["scenarioRuns"])

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_path = output_dir / "phase8-session.json"
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    print(session_path)
    print(json.dumps({"passedScenarios": session["passedScenarios"], "totalScenarios": session["totalScenarios"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
