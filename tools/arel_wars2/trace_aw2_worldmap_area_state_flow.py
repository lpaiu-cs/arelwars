from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_area_state_flow.json"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"


def build_report() -> dict[str, object]:
    return {
        "sourceLib": str(ORIGINAL_LIB),
        "isCheckAreaEnter": {
            "symbol": "_ZN16CPdStateWorldmap16IsCheckAreaEnterEi",
            "range": ["0x0d22d4", "0x0d22f0"],
            "rules": [
                "area == 5 returns true immediately",
                "otherwise the function compares a global progress field against (areaIndex * 15)",
                "for non-negative progress values, the effective result is true when globalProgress24 >= areaIndex * 15",
            ],
            "notes": [
                "This is an area-enter gate, not a stage-select creator.",
                "The area-5 fast path matches the special pendingArea_5 branch later seen in UpdateWorldMapMenu.",
            ],
        },
        "initWorldmapSltAreaAni": {
            "symbol": "_ZN16CPdStateWorldmap22InitWorldmapSltAreaAniEi",
            "range": ["0x0d22f8", "0x0d2398"],
            "reads": {
                "selectedAreaField": "0x100",
            },
            "notes": [
                "The helper immediately re-checks the currently selected area through IsCheckAreaEnter(this->selectedArea).",
                "This means a first-hit area change only initializes selection animation/state; it does not itself request stage select.",
            ],
        },
        "areaFields": {
            "selectedAreaField": {
                "offset": "0x100",
                "writers": [
                    "_ZN16CPdStateWorldmapC1Ev",
                    "_ZN16CPdStateWorldmapC2Ev",
                    "_ZN16CPdStateWorldmap19Select_WorldmapMenuEv",
                    "_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii",
                ],
                "readers": [
                    "_ZN16CPdStateWorldmap22InitWorldmapSltAreaAniEi",
                    "_ZN16CPdStateWorldmap19Select_WorldmapMenuEv",
                    "_ZN16CPdStateWorldmap16DrawWorldMapMenuEv",
                    "_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii",
                ],
            },
            "selectedAreaMirrorField": {
                "offset": "0x361c",
                "writers": [
                    "_ZN16CPdStateWorldmap10InitializeEv",
                    "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv",
                ],
                "readers": [
                    "_ZN16CPdStateWorldmap9CloseMenuE17EnumWorldMapState",
                    "_ZN16CPdStateWorldmap21MakeBufferStageSelectEv",
                    "_ZN16CPdStateWorldmap13DrawStageInfoEv",
                ],
                "notes": [
                    "The generic area-entry path mirrors the pending area into 0x361c before it requests pending state 2.",
                    "MakeBufferStageSelect is the strongest static consumer of this mirrored area index.",
                ],
            },
            "pendingAreaField": {
                "offset": "0x36f8",
                "writers": [
                    "_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii",
                    "_ZN16CPdStateWorldmap16OnPointerReleaseEP12GxPointerPos",
                ],
                "readers": [
                    "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv",
                ],
            },
        },
        "updateWorldMapMenu": {
            "symbol": "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv",
            "range": ["0x10b764", "0x10b8e4"],
            "pendingAreaCases": {
                "0_to_4": [
                    "mirror pending area into [this+0x361c]",
                    "set [this+0x8] = 2",
                    "copy [this+0x4] into [this+0xc]",
                    "clear [this+0x36f8] = -1",
                ],
                "5": [
                    "set [this+0x8] = 0x19",
                    "copy [this+0x4] into [this+0xc]",
                    "clear [this+0x36f8] = -1",
                ],
            },
            "notes": [
                "The 0..4 path is the generic area-selection path.",
                "The area-5 path is a special-case worldmap branch and is the strongest current match for the live Town SHOP-style response.",
            ],
        },
        "makeBufferStageSelect": {
            "symbol": "_ZN16CPdStateWorldmap21MakeBufferStageSelectEv",
            "range": ["0x0eba88", "0x0ebc80"],
            "reads": {
                "selectedAreaMirrorField": "0x361c",
                "currentStateField": "0x4",
            },
            "notes": [
                "The function repeatedly indexes stage-select assets using [this+0x361c].",
                "It explicitly special-cases [this+4] == 2 while building the stage-select presentation state.",
                "This makes state 2 the confirmed generic world-area -> stage-select preparation state.",
            ],
        },
        "conclusion": [
            "Town SHOP responding while DESERT PLAIN/PVP do not is consistent with the special pendingArea_5 branch working while the generic 0..4 area path remains blocked.",
            "The next safe targets are selected-area latching (0x100), same-area re-tap arming (0x379c/0x36f8), and pending-state 2 consumption, not direct CreateStageSelect forcing.",
        ],
    }


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(build_report(), indent=2), encoding="utf-8")
    print(str(REPORT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
