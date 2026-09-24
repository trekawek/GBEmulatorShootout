"""Stable metadata used by the runner export and the static site builder."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from catalog import EMULATORS as CATALOG_EMULATORS


SCHEMA_VERSION = 1
SCORE_POLICY = "legacy-nonfail-v1"


SUITES = [
    {
        "id": "acid",
        "name": "Acid tests",
        "sources": [
            {"label": "dmg-acid2", "url": "https://github.com/mattcurrie/dmg-acid2"},
            {"label": "cgb-acid2", "url": "https://github.com/mattcurrie/cgb-acid2"},
            {"label": "cgb-acid-hell", "url": "https://github.com/mattcurrie/cgb-acid-hell"},
        ],
    },
    {
        "id": "blargg",
        "name": "Blargg's tests",
        "sources": [{"label": "Source", "url": "https://github.com/retrio/gb-test-roms"}],
    },
    {
        "id": "daid",
        "name": "Daid's tests",
        "sources": [
            {
                "label": "Source",
                "url": "https://github.com/gbdev/GBEmulatorShootout/tree/main/testroms/daid",
            }
        ],
    },
    {
        "id": "ax6",
        "name": "MBC3 RTC tests",
        "sources": [{"label": "Source", "url": "https://github.com/aaaaaa123456789/rtc3test"}],
    },
    {
        "id": "mooneye",
        "name": "Mooneye",
        "sources": [{"label": "Source", "url": "https://github.com/Gekkio/mooneye-test-suite"}],
    },
    {
        "id": "samesuite",
        "name": "SameSuite",
        "sources": [{"label": "Source", "url": "https://github.com/LIJI32/SameSuite"}],
    },
    {
        "id": "ashiepaws",
        "name": "Ashiepaws' tests",
        "sources": [
            {"label": "BullyGB", "url": "https://github.com/Ashiepaws/BullyGB"},
            {"label": "Strikethrough", "url": "https://github.com/Ashiepaws/strikethrough.gb"},
        ],
    },
    {
        "id": "cpp",
        "name": "CasualPokePlayer's tests",
        "sources": [{"label": "Source", "url": "https://github.com/CasualPokePlayer/test-roms"}],
    },
    {
        "id": "mealybug-tearoom-tests",
        "name": "Mealybug Tearoom",
        "sources": [
            {"label": "Source", "url": "https://github.com/mattcurrie/mealybug-tearoom-tests"}
        ],
    },
    {
        "id": "legacy-unmapped",
        "name": "Unmapped legacy tests",
        "sources": [],
    },
]


EMULATORS = {
    spec.name: {"id": spec.page_id, "systems": spec.site_systems}
    for spec in CATALOG_EMULATORS
}


def slug(value: str, *, limit: int = 72) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"
    if len(normalized) <= limit:
        return normalized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[:limit - 9].rstrip('-')}-{digest}"


def test_id(name: str, model: str) -> str:
    """Return a stable case ID while keeping collisions human-auditable."""
    digest = hashlib.sha256(f"{name}\0{model}".encode("utf-8")).hexdigest()[:8]
    return f"{slug(name, limit=63)}-{model.lower()}-{digest}"


def suite_id_for(name: str) -> str:
    candidate = name.split("/", 1)[0]
    known = {suite["id"] for suite in SUITES}
    return candidate if candidate in known else "legacy-unmapped"


def case_parts(name: str) -> tuple[str, str]:
    parts = name.split("/")
    case_name = parts[-1]
    group = "/".join(parts[1:-1]) if len(parts) > 2 else ""
    return case_name, group


def test_to_metadata(test) -> dict:
    name = str(test)
    model = str(test.model).upper()
    case_name, group = case_parts(name)
    return {
        "id": test_id(name, model),
        "legacyName": name,
        "name": case_name,
        "suiteId": suite_id_for(name),
        "group": group,
        "system": model.lower(),
        "requiredFeatures": sorted(test.required_features),
        "description": test.description,
        "sourceUrl": test.url,
        "expectedPaths": list(test.expected_paths),
    }


def current_test_metadata() -> list[dict]:
    """Load test declarations without importing the GUI-heavy runner module."""
    import importlib
    import sys
    import types

    class DeclaredTest:
        def __init__(
            self,
            name,
            *,
            runtime,
            rom=None,
            result=None,
            model="DMG",
            required_features=None,
            description=None,
            url=None,
            tags=None,
        ):
            self.name = name
            self.model = model
            self.required_features = set(required_features or ())
            self.description = description
            self.url = url
            if result is None:
                result = os.path.splitext(rom or name)[0] + ".png"
            candidates = result if isinstance(result, list) else [result]
            root = Path(__file__).parent / "testroms"
            self.expected_paths = [
                str(Path("testroms") / candidate)
                for candidate in candidates
                if (root / candidate).is_file()
            ]

        def __str__(self):
            return self.name

    declaration_module = types.ModuleType("test")
    declaration_module.Test = DeclaredTest
    declaration_module.DMG = "DMG"
    declaration_module.CGB = "CGB"
    declaration_module.SGB = "SGB"
    declaration_module.PCM = "PCM"
    declaration_module.PASS = "PASS"
    declaration_module.FAIL = "FAIL"
    declaration_module.INFO = "INFO"

    original_test_module = sys.modules.get("test")
    sys.modules["test"] = declaration_module
    module_names = (
        "acid",
        "blargg",
        "daid",
        "ax6",
        "mooneye",
        "samesuite",
        "ashiepaws",
        "cpp",
        "mealybug",
    )
    try:
        modules = [importlib.import_module(f"testroms.{name}") for name in module_names]
    finally:
        if original_test_module is None:
            sys.modules.pop("test", None)
        else:
            sys.modules["test"] = original_test_module

    declared = [test for module in modules for test in module.all]
    return [test_to_metadata(test) for test in declared]
