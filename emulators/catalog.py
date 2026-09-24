"""The active emulator list and its report and CI metadata.

Keep this module free of adapter imports so CI can read it without installing
Windows-only dependencies. Adapter modules are imported only when selected.
"""

import ast
import json
import os
import re
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path


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
    needs_audio: bool = True
    needs_chromedriver: bool = False
    extra_requirements: str = ""

    @property
    def keywords(self):
        return (self.id, self.name, *self.aliases)

    @property
    def result_filename(self):
        return result_filename(self.name)

    def create(self):
        module_name, class_name = self.adapter.rsplit(":", 1)
        return getattr(import_module(module_name), class_name)(self)

    def ci_entry(self):
        return {
            "emulator": self.id,
            "needs_audio": self.needs_audio,
            "needs_chromedriver": self.needs_chromedriver,
            "extra_requirements": self.extra_requirements,
        }


EMULATORS = (
    EmulatorSpec("bdm", "Beaten Dying Moon", "https://mattcurrie.com/bdm-demo/", "emulators.bdm:BDM", aliases=("beaten",)),
    EmulatorSpec("mgba", "mGBA", "https://mgba.io/", "emulators.mgba:MGBA"),
    EmulatorSpec("kigb", "KiGB", "http://kigb.emuunlim.com/", "emulators.kigb:KiGB"),
    EmulatorSpec("sameboy", "SameBoy", "https://sameboy.github.io/", "emulators.sameboy:SameBoy"),
    EmulatorSpec("bgb", "bgb", "https://bgb.bircd.org/", "emulators.bgb:BGB"),
    EmulatorSpec("vba", "VisualBoyAdvance", "https://sourceforge.net/projects/vba", "emulators.vba:VBA", needs_audio=False),
    EmulatorSpec("vbam", "VisualBoyAdvance-M", "https://github.com/visualboyadvance-m/visualboyadvance-m", "emulators.vba:VBAM"),
    EmulatorSpec("nocash", "No$gmb", "https://problemkaputt.de/gmb.htm", "emulators.nocash:NoCash"),
    EmulatorSpec("gambatte", "GambatteSpeedrun", "https://github.com/pokemon-speedrunning/gambatte-speedrun", "emulators.gambatte:GambatteSpeedrun"),
    EmulatorSpec("emulicious", "Emulicious", "https://emulicious.net/", "emulators.emulicious:Emulicious"),
    EmulatorSpec("goomba", "Goomba", "https://www.dwedit.org/gba/goombacolor.php", "emulators.goomba:Goomba"),
    EmulatorSpec("binjgb", "binjgb", "https://github.com/binji/binjgb", "emulators.binjgb:Binjgb"),
    EmulatorSpec("pyboy", "PyBoy", "https://github.com/Baekalfen/PyBoy", "emulators.pyboy:PyBoy"),
    EmulatorSpec("ares", "ares", "https://ares-emu.net/", "emulators.ares:Ares"),
    EmulatorSpec("emmy", "Emmy", "https://emmy.n1ark.com/", "emulators.emmy:Emmy", needs_audio=False, needs_chromedriver=True, extra_requirements="requirements-emmy.txt"),
    EmulatorSpec("gameroy", "gameroy", "https://github.com/Rodrigodd/gameroy", "emulators.gameroy:GameRoy"),
    EmulatorSpec("docboy", "DocBoy", "https://github.com/Docheinstein/docboy", "emulators.docboy:DocBoy"),
    EmulatorSpec("gse", "GSE", "https://github.com/CasualPokePlayer/GSE", "emulators.gse:GSE", aliases=("Game Boy Speedrun Emulator",)),
)


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
    filenames = set()
    keywords = {}
    for spec in EMULATORS:
        if not re.fullmatch(r"[a-z0-9_-]+", spec.id):
            raise ValueError("Invalid emulator ID: %s" % spec.id)
        if spec.id in ids or spec.result_filename in filenames:
            raise ValueError("Duplicate emulator ID or result filename: %s" % spec.id)
        ids.add(spec.id)
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
        if spec.extra_requirements and not (Path(__file__).resolve().parent.parent / spec.extra_requirements).is_file():
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
