#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ORACLE_SESSION = REPO_ROOT / "recovery" / "arel_wars2" / "native_tmp" / "oracle" / "first-scene-v1" / "session.json"
DEFAULT_BOOTSTRAP_TRACE = REPO_ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2-bootstrap-trace.json"
DEFAULT_OUTPUT = REPO_ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2-launcher-boundary-comparison.json"
DEFAULT_ORACLE_UI = REPO_ROOT / "recovery" / "arel_wars2" / "native_tmp" / "oracle" / "aw2-original-network-error.xml"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_texts(xml_path: Path) -> list[str]:
    try:
        raw = xml_path.read_bytes()
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                xml_text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                xml_text = None
        if xml_text is None:
            return []
        end_tag = "</hierarchy>"
        end_index = xml_text.find(end_tag)
        if end_index != -1:
            xml_text = xml_text[: end_index + len(end_tag)]
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    texts: list[str] = []
    for node in root.iter("node"):
        text = node.attrib.get("text")
        if text:
            texts.append(text)
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare original AW2 first-scene oracle boundary against bootstrap trace.")
    parser.add_argument("--oracle-session", type=Path, default=DEFAULT_ORACLE_SESSION)
    parser.add_argument("--oracle-ui", type=Path, default=DEFAULT_ORACLE_UI)
    parser.add_argument("--bootstrap-trace", type=Path, default=DEFAULT_BOOTSTRAP_TRACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    oracle_session = read_json(args.oracle_session)
    bootstrap_trace = read_json(args.bootstrap_trace)

    post_start = args.oracle_ui if args.oracle_ui.exists() else Path(oracle_session["steps"][-1]["uiPath"])
    post_start_texts = parse_texts(post_start)
    original_resumed = oracle_session.get("finalResumedActivity", "")
    bootstrap_scene = bootstrap_trace.get("sceneLabel")
    verification = bootstrap_trace.get("verificationTrace", {})

    result = {
        "specVersion": "aw2-launcher-boundary-compare-v1",
        "oracleSessionPath": str(args.oracle_session),
        "bootstrapTracePath": str(args.bootstrap_trace),
        "original": {
            "finalResumedActivity": original_resumed,
            "launcherReached": ".ArelWars2Launcher" in original_resumed,
            "networkErrorSeen": "Network Error" in post_start_texts,
            "networkMessageSeen": any("Cannot run the program." in text for text in post_start_texts),
            "texts": post_start_texts,
        },
        "bootstrap": {
            "sceneLabel": bootstrap_scene,
            "launcherReached": bootstrap_scene == "ArelWars2Launcher",
            "familyId": verification.get("familyId"),
            "aiIndex": verification.get("aiIndex"),
            "routeLabel": verification.get("routeLabel"),
            "preferredMapIndex": verification.get("preferredMapIndex"),
            "resumeTargetScene": verification.get("resumeTargetScene"),
            "resumeTargetStageBinding": verification.get("resumeTargetStageBinding"),
        },
    }
    result["boundaryMatch"] = {
        "launcherReachedBoth": result["original"]["launcherReached"] and result["bootstrap"]["launcherReached"],
        "externalNetworkGateAcknowledged": result["original"]["networkErrorSeen"] and result["original"]["networkMessageSeen"],
        "bootstrapSeedPresent": result["bootstrap"]["familyId"] is not None and result["bootstrap"]["preferredMapIndex"] is not None,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
