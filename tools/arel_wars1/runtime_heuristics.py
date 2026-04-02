from __future__ import annotations

from typing import Any


OPCODE_ACTION_OVERRIDES: dict[str, dict[str, Any]] = {
    "cmd-00": {
        "label": "mixed-battlefield-selector",
        "action": "select-contextual-battlefield-focus",
        "category": "ui-focus",
        "confidence": "low",
        "notes": [
            "Variant 0x0d is strongly tied to the battle-HUD tutorial chain, but other uses remain mixed.",
            "Treat the mnemonic-wide label as a selector family, not a final engine-name claim.",
        ],
    },
    "cmd-02": {
        "label": "tutorial-focus-anchor",
        "action": "guided-highlight-anchor",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Clusters around tutorial scripts and explicit touch or HUD instructions.",
            "Best current reading is a guided focus or highlighted subject anchor.",
        ],
    },
    "cmd-05": {
        "label": "dialogue-pose-helper",
        "action": "apply-dialogue-pose",
        "category": "presentation",
        "confidence": "medium",
        "notes": [
            "Usually follows portrait selection and is usually closed by cmd-08.",
            "Best current reading is a dialogue pose, mouth, or focus helper.",
        ],
    },
    "cmd-06": {
        "label": "tutorial-focus-prelude",
        "action": "enter-guided-focus-mode",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Appears heavily in tutorial scripts with arrows, cards, and menu references.",
            "Best current reading is a submode or target selector for tutorial focus.",
        ],
    },
    "cmd-07": {
        "label": "mixed-tower-selector",
        "action": "focus-tower-menu-or-related-ui-slot",
        "category": "ui-focus",
        "confidence": "low",
        "notes": [
            "Variant 0x40 is strongly tied to the Tower menu tutorial highlight.",
            "The wider opcode family is still not proven outside mirrored tutorial chains.",
        ],
    },
    "cmd-08": {
        "label": "mixed-presentation-or-upgrade-target",
        "action": "release-dialogue-pose-or-focus-upgrade-slot",
        "category": "presentation",
        "confidence": "medium",
        "notes": [
            "Frequently terminates pose-helper sequences that include cmd-05.",
            "Variant 0x40 is a strong tutorial highlight for the Mana upgrade icon.",
        ],
    },
    "cmd-09": {
        "label": "mixed-population-selector",
        "action": "focus-population-upgrade-or-related-ui-slot",
        "category": "ui-focus",
        "confidence": "low",
        "notes": [
            "Variant 0x40 is strongly tied to Upgrade Population in the menu tutorial.",
            "The opcode family is not yet globally proven outside the tutorial path.",
        ],
    },
    "cmd-0a": {
        "label": "mixed-emphasis-cue",
        "action": "start-emphasis-or-ui-target",
        "category": "emphasis",
        "confidence": "medium",
        "notes": [
            "Acts like an emphasis helper in dramatic scenes but also shows up in tutorial target chains.",
            "Variant-level interpretation is safer than a global rename.",
        ],
    },
    "cmd-0b": {
        "label": "mixed-emphasis-release",
        "action": "release-emphasis-or-focus-skill-slot",
        "category": "emphasis",
        "confidence": "medium",
        "notes": [
            "Pairs strongly with cmd-0a in shock or impact lines.",
            "Variant 0x40 is a strong tutorial highlight for the active skill window.",
        ],
    },
    "cmd-0c": {
        "label": "tutorial-target-anchor",
        "action": "bind-guided-target",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Appears in tutorial and scripted explanation contexts with cmd-02 and cmd-00.",
            "Best current reading is a tutorial anchor or focus target opcode.",
        ],
    },
    "cmd-0d": {
        "label": "mixed-system-selector",
        "action": "focus-system-menu-or-scene-slot",
        "category": "ui-focus",
        "confidence": "low",
        "notes": [
            "Variant 0x40 is strongly tied to the System menu tutorial highlight.",
            "Variant 0x00 still appears in generic scene-opening chains, so the family remains mixed.",
        ],
    },
    "cmd-0e": {
        "label": "mixed-quest-selector",
        "action": "focus-quest-panel-or-scene-slot",
        "category": "ui-focus",
        "confidence": "low",
        "notes": [
            "Variant 0x40 is strongly tied to the quest panel and rewards tutorial chain.",
            "Variant 0x00 also appears as a generic scene-opening opcode, so the family remains mixed.",
        ],
    },
    "cmd-10": {
        "label": "scene-entry-preset",
        "action": "load-scene-entry-layout",
        "category": "scene-bootstrap",
        "confidence": "low",
        "notes": [
            "Frequently appears at scene openings before portrait or pose helpers.",
            "Best current reading is a scene-entry layout or camera preset.",
        ],
    },
    "cmd-18": {
        "label": "banter-entry-preset",
        "action": "load-banter-entry-layout",
        "category": "scene-bootstrap",
        "confidence": "medium",
        "notes": [
            "Almost always appears at the start of a scene line and then yields to a normal portrait chain.",
            "Best current reading is a lighter scene-entry or banter preset variant.",
        ],
    },
    "cmd-43": {
        "label": "tutorial-bootstrap",
        "action": "enter-tutorial-narration",
        "category": "scene-bootstrap",
        "confidence": "medium",
        "notes": [
            "Appears at tutorial openings before chained focus helpers.",
            "Best current reading is a tutorial bootstrap or narrator mode switch.",
        ],
    },
}

OPCODE_VARIANT_OVERRIDES: dict[str, dict[str, Any]] = {
    "cmd-00:0d": {
        "label": "battle-hud-focus-prelude",
        "action": "enter-battle-hud-focus-mode",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Repeated across `0004`, `0404`, and `0804` before tower HP, unit-card, mana-bar, sortie, and return-to-tower lines.",
        ],
    },
    "cmd-02:05": {
        "label": "tutorial-highlight-subject",
        "action": "focus-current-tutorial-subject",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Common on tutorial lines that explain HP bars, mana, and production targets.",
        ],
    },
    "cmd-05:03": {
        "label": "dialogue-pose-neutral",
        "action": "apply-neutral-dialogue-pose",
        "category": "presentation",
        "confidence": "medium",
        "notes": [
            "Common after left-portrait setup in ordinary dialogue scenes.",
        ],
    },
    "cmd-06:0d": {
        "label": "tutorial-focus-prelude",
        "action": "enter-guided-focus-mode",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Repeatedly appears in `0004` and `0014` around arrows, mana, cards, and menu instructions.",
        ],
    },
    "cmd-07:40": {
        "label": "tower-menu-highlight",
        "action": "focus-tower-upgrade-menu",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Tied to tutorial lines about tower icons and upgrades.",
        ],
    },
    "cmd-08:40": {
        "label": "mana-upgrade-highlight",
        "action": "focus-mana-upgrade-slot",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about Mana regeneration speed and max Mana.",
        ],
    },
    "cmd-08:00": {
        "label": "presentation-close",
        "action": "release-dialogue-pose",
        "category": "presentation",
        "confidence": "high",
        "notes": [
            "Overwhelmingly ends a cmd-05 presentation chain.",
        ],
    },
    "cmd-09:40": {
        "label": "population-upgrade-highlight",
        "action": "focus-population-upgrade-slot",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about hitting max population and unit production capacity.",
        ],
    },
    "cmd-0a:10": {
        "label": "emphasis-start",
        "action": "start-shock-or-impact-cue",
        "category": "emphasis",
        "confidence": "high",
        "notes": [
            "Appears around surprise, pain, and forceful lines.",
        ],
    },
    "cmd-0a:40": {
        "label": "skill-menu-highlight",
        "action": "focus-skill-menu",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines like `Let's check your skills.`",
        ],
    },
    "cmd-0b:10": {
        "label": "emphasis-end",
        "action": "release-shock-or-impact-cue",
        "category": "emphasis",
        "confidence": "high",
        "notes": [
            "Usually paired with cmd-0a(0x10) around abrupt reactions.",
        ],
    },
    "cmd-0b:40": {
        "label": "skill-slot-highlight",
        "action": "focus-skill-window-slot",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about touching a skill in the battle skill window.",
        ],
    },
    "cmd-0c:40": {
        "label": "item-menu-highlight",
        "action": "focus-item-menu",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about equipped items before battle.",
        ],
    },
    "cmd-0d:40": {
        "label": "system-menu-highlight",
        "action": "focus-system-menu",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about pausing, resuming, and configuration settings.",
        ],
    },
    "cmd-0e:40": {
        "label": "quest-panel-highlight",
        "action": "focus-quest-panel",
        "category": "ui-focus",
        "confidence": "high",
        "notes": [
            "Appears on tutorial lines about quest rewards on the upper-right side.",
        ],
    },
    "cmd-10:00": {
        "label": "scene-entry-preset",
        "action": "load-scene-entry-layout",
        "category": "scene-bootstrap",
        "confidence": "medium",
        "notes": [
            "Frequent opening marker before portrait setup.",
        ],
    },
    "cmd-18:00": {
        "label": "banter-entry-preset",
        "action": "load-banter-entry-layout",
        "category": "scene-bootstrap",
        "confidence": "medium",
        "notes": [
            "Start-of-scene marker concentrated in lighter dialogue transitions.",
        ],
    },
    "cmd-43:00": {
        "label": "tutorial-bootstrap",
        "action": "enter-tutorial-narration",
        "category": "scene-bootstrap",
        "confidence": "high",
        "notes": [
            "Seen at the start of tutorial explanation scripts.",
        ],
    },
}

RUNTIME_FEATURED_MNEMONICS = [
    "cmd-00",
    "cmd-02",
    "cmd-05",
    "cmd-06",
    "cmd-07",
    "cmd-08",
    "cmd-09",
    "cmd-0a",
    "cmd-0b",
    "cmd-0c",
    "cmd-0d",
    "cmd-0e",
    "cmd-10",
    "cmd-18",
    "cmd-43",
]

FEATURED_ARCHETYPES = [
    "dispatch",
    "tower-defense",
    "naturalhealing",
    "recall",
    "hpup",
    "returntonature",
    "manawall",
    "armageddon",
    "managain",
    "special-stun",
    "special-smoke",
    "special-armageddonbuff",
]


def map_group_for_variant(variant_candidate: int) -> int:
    if variant_candidate <= 1:
        return 0
    if variant_candidate == 2:
        return 1
    if variant_candidate == 3:
        return 2
    if variant_candidate == 4:
        return 3
    return 4


def render_intensity_label(region_candidate: int, tier_candidate: int, story_flag_candidate: int) -> str:
    if tier_candidate >= 50 or region_candidate >= 9:
        return "high"
    if story_flag_candidate == 1:
        return "medium"
    return "low"
