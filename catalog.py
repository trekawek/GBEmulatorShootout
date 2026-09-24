"""Load emulator metadata for the runner, report, and CI from catalog.yaml.

Keep this module free of adapter imports so CI can read it without installing
Windows-only dependencies. Adapter modules are imported only when selected.
"""

import ast
import json
import os
import re
from dataclasses import dataclass, fields
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import yaml


CATALOG_PATH = Path(__file__).with_suffix(".yaml")


def normalize(value):
    return "".join(char for char in str(value).lower() if char.isalnum())


def result_filename(name):
    # Keep filenames compatible with results already published on gh-pages.
    return "%s.json" % name.replace(" ", "_").lower()


@dataclass(frozen=True)
class EmulatorSpec:
    id: str
    name: str
    url: str
    adapter: str
    aliases: tuple = ()
    site_id: str = ""
    systems: tuple = (None, None, None)
    needs_audio: bool = True
    needs_chromedriver: bool = False
    needs_java: bool = False
    timeout_minutes: int = 360
    extra_requirements: str = ""

    @property
    def keywords(self):
        return (self.id, self.name, *self.aliases)

    @property
    def result_filename(self):
        return result_filename(self.name)

    @property
    def page_id(self):
        return self.site_id or self.id

    @property
    def site_systems(self):
        return dict(zip(("dmg", "cgb", "sgb"), self.systems))

    def create(self):
        module_name, class_name = self.adapter.rsplit(":", 1)
        return getattr(import_module(module_name), class_name)(self)

    def ci_entry(self):
        return {
            "emulator": self.id,
            "needs_audio": self.needs_audio,
            "needs_chromedriver": self.needs_chromedriver,
            "needs_java": self.needs_java,
            "timeout_minutes": self.timeout_minutes,
            "extra_requirements": self.extra_requirements,
        }


def load_emulators(path=CATALOG_PATH):
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError("Cannot read emulator catalog %s: %s" % (path, error)) from error
    if not isinstance(document, dict) or set(document) != {"emulators"}:
        raise ValueError("Emulator catalog must contain only an 'emulators' list")
    entries = document["emulators"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("Emulator catalog must contain at least one emulator")

    required = {"id", "name", "url", "adapter"}
    allowed = {field.name for field in fields(EmulatorSpec)}
    specs = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("Emulator entry %d must be a mapping" % index)
        missing = required - entry.keys()
        unknown = entry.keys() - allowed
        if missing or unknown:
            raise ValueError("Emulator entry %d has missing fields %s or unknown fields %s" % (index, sorted(missing), sorted(unknown)))
        for key in required | {"site_id", "extra_requirements"}:
            value = entry.get(key, "")
            if not isinstance(value, str) or (key in required and not value):
                raise ValueError("Emulator entry %d has an invalid %s" % (index, key))
        for key in ("needs_audio", "needs_chromedriver", "needs_java"):
            if key in entry and type(entry[key]) is not bool:
                raise ValueError("Emulator entry %d has an invalid %s" % (index, key))
        if "timeout_minutes" in entry and (type(entry["timeout_minutes"]) is not int or entry["timeout_minutes"] <= 0):
            raise ValueError("Emulator entry %d has an invalid timeout_minutes" % index)
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            raise ValueError("Emulator entry %d has invalid aliases" % index)
        systems = entry.get("systems", {model: None for model in ("dmg", "cgb", "sgb")})
        if (not isinstance(systems, dict) or set(systems) != {"dmg", "cgb", "sgb"}
                or any(value is not None and type(value) is not bool for value in systems.values())):
            raise ValueError("Emulator entry %d has invalid systems" % index)
        specs.append(EmulatorSpec(**{
            **entry,
            "aliases": tuple(aliases),
            "systems": tuple(systems[model] for model in ("dmg", "cgb", "sgb")),
        }))
    return tuple(specs)


EMULATORS = load_emulators()


def matching_emulators(filters=None):
    if filters is None:
        return list(EMULATORS)

    excluded = {normalize(value[1:]) for value in filters if value.startswith("!")}
    included = {normalize(value) for value in filters if not value.startswith("!")}
    matches = []
    for spec in EMULATORS:
        keywords = {normalize(value) for value in spec.keywords}
        if keywords & excluded:
            continue
        if excluded or keywords & included:
            matches.append(spec)
    return matches


def ci_matrix(selection="all"):
    if selection == "all":
        specs = EMULATORS
    else:
        specs = matching_emulators([selection])
        if len(specs) != 1:
            raise ValueError("Unknown or ambiguous emulator: %s" % selection)
    return {"include": [spec.ci_entry() for spec in specs]}


def validate_catalog():
    ids = set()
    page_ids = set()
    filenames = set()
    keywords = {}
    for spec in EMULATORS:
        if not re.fullmatch(r"[a-z0-9_-]+", spec.id):
            raise ValueError("Invalid emulator ID: %s" % spec.id)
        if spec.id in ids or spec.result_filename in filenames:
            raise ValueError("Duplicate emulator ID or result filename: %s" % spec.id)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", spec.page_id) or spec.page_id in page_ids:
            raise ValueError("Invalid or duplicate site ID: %s" % spec.page_id)
        ids.add(spec.id)
        page_ids.add(spec.page_id)
        filenames.add(spec.result_filename)
        if ":" not in spec.adapter:
            raise ValueError("Invalid adapter path: %s" % spec.adapter)
        module_name, class_name = spec.adapter.rsplit(":", 1)
        module = find_spec(module_name)
        if module is None or module.origin is None:
            raise ValueError("Adapter module not found: %s" % module_name)
        source = ast.parse(Path(module.origin).read_text(encoding="utf-8"))
        if not any(isinstance(node, ast.ClassDef) and node.name == class_name for node in source.body):
            raise ValueError("Adapter class not found: %s" % spec.adapter)
        if spec.extra_requirements and not (Path(__file__).resolve().parent / spec.extra_requirements).is_file():
            raise ValueError("Requirements file not found: %s" % spec.extra_requirements)
        for keyword in spec.keywords:
            normalized = normalize(keyword)
            if not normalized:
                raise ValueError("Empty emulator keyword: %s" % spec.id)
            if normalized in keywords and keywords[normalized] != spec.id:
                raise ValueError("Ambiguous emulator keyword: %s" % keyword)
            keywords[normalized] = spec.id


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("ci-matrix", "validate"))
    args = parser.parse_args()
    try:
        validate_catalog()
        if args.command == "ci-matrix":
            print("matrix=" + json.dumps(ci_matrix(os.environ.get("EMULATOR_SELECTION") or "all"), separators=(",", ":")))
    except ValueError as error:
        parser.error(str(error))
