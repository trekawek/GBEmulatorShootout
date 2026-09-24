"""Build the static GitHub Pages site from emulator result JSON files."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path

from site_metadata import (
    EMULATORS,
    SCHEMA_VERSION,
    SCORE_POLICY,
    SUITES,
    case_parts,
    current_test_metadata,
    suite_id_for,
    test_id,
)


STATUS_MAP = {"PASS": "pass", "FAIL": "fail", "INFO": "info"}
STATIC_FILES = ("index.html", "emulator.html", "assets")


def read_json(path: Path):
    with path.open("rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wt", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def iso_timestamp(value) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("screenshot is not a PNG")
    return struct.unpack(">II", data[16:24])


def decode_screenshot(value: str | None) -> bytes | None:
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid base64 screenshot") from error


def load_catalog_tests(tests_path: Path) -> list[dict]:
    exported = read_json(tests_path)
    current = {item["legacyName"]: item for item in current_test_metadata()}
    tests = []
    seen_ids = set()

    for exported_item in exported:
        legacy_name = exported_item.get("legacyName", exported_item.get("name"))
        if not legacy_name:
            raise ValueError("test metadata entry has no legacy name")

        if "id" in exported_item and "system" in exported_item:
            item = dict(exported_item)
            if "expectedPaths" not in item and legacy_name in current:
                item["expectedPaths"] = current[legacy_name]["expectedPaths"]
        elif legacy_name in current:
            item = dict(current[legacy_name])
            item["description"] = exported_item.get("description", item["description"])
            item["sourceUrl"] = exported_item.get("url", item["sourceUrl"])
        else:
            case_name, group = case_parts(legacy_name)
            system = "cgb" if "(GBC)" in legacy_name or "(CGB" in legacy_name else "dmg"
            item = {
                "id": test_id(legacy_name, system.upper()),
                "legacyName": legacy_name,
                "name": case_name,
                "suiteId": suite_id_for(legacy_name),
                "group": group,
                "system": system,
                "requiredFeatures": [],
                "description": exported_item.get("description"),
                "sourceUrl": exported_item.get("url"),
            }

        if item["id"] in seen_ids:
            raise ValueError(f"duplicate test ID: {item['id']}")
        seen_ids.add(item["id"])
        tests.append(item)

    return tests


def publish_reference_images(tests: list[dict], output_dir: Path) -> None:
    """Move local reference paths into root-relative catalog URLs."""
    source_root = (Path(__file__).parent / "testroms").resolve()
    for test in tests:
        expected = []
        for filename in test.pop("expectedPaths", []):
            source = (Path(__file__).parent / filename).resolve()
            if source.suffix.lower() != ".png" or not source.is_relative_to(source_root):
                raise ValueError(f"unsafe reference image path: {filename!r}")
            if not source.is_file():
                raise ValueError(f"missing reference image: {filename!r}")
            relative = Path("references") / source.relative_to(source_root)
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            width, height = png_size(source.read_bytes())
            expected.append({"url": relative.as_posix(), "width": width, "height": height})
        test["expected"] = expected


def catalog_id_for(tests: list[dict], suites: list[dict]) -> str:
    canonical = json.dumps(
        {"suites": suites, "tests": tests}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "catalog-" + hashlib.sha256(canonical).hexdigest()[:12]


def validate_relative_filename(value: str) -> str:
    if not value or Path(value).name != value:
        raise ValueError(f"unsafe result filename: {value!r}")
    return value


def result_case_metadata(name: str, catalog_by_name: dict[str, dict]) -> dict:
    known = catalog_by_name.get(name)
    if known:
        return known
    case_name, group = case_parts(name)
    system = "cgb" if "(GBC)" in name or "(CGB" in name else "unknown"
    return {
        "id": test_id(name, system.upper()),
        "legacyName": name,
        "name": case_name,
        "suiteId": "legacy-unmapped",
        "group": group,
        "system": system,
        "requiredFeatures": [],
        "description": None,
        "sourceUrl": None,
    }


def result_record(case: dict, raw: dict | None, screenshot=None) -> dict:
    if raw is None:
        status = "missing"
        reason = "No result was recorded; the legacy data does not identify why."
    else:
        raw_status = raw.get("result")
        if raw_status not in STATUS_MAP:
            raise ValueError(f"unexpected legacy status {raw_status!r} for {case['legacyName']}")
        status = STATUS_MAP[raw_status]
        reason = None
    return {
        "testId": case["id"],
        "legacyName": case["legacyName"],
        "name": case["name"],
        "suiteId": case["suiteId"],
        "group": case["group"],
        "system": case["system"],
        "description": case.get("description"),
        "sourceUrl": case.get("sourceUrl"),
        "status": status,
        "reason": reason,
        "startupSeconds": raw.get("startuptime") if raw else None,
        "runtimeSeconds": raw.get("runtime") if raw else None,
        "screenshot": screenshot,
    }


def build_emulator_result(
    *, emulator_id: str, source: dict, catalog_tests: list[dict], output_dir: Path, catalog_id: str
) -> tuple[dict, dict]:
    raw_tests = source.get("tests", {})
    if not isinstance(raw_tests, dict):
        raise ValueError(f"results for {emulator_id} have no test object")

    tested_at = iso_timestamp(source.get("date"))
    timestamp_part = str(int(float(source.get("date", 0)))) if source.get("date") is not None else "unknown"
    run_id = f"legacy-{timestamp_part}"
    catalog_by_name = {item["legacyName"]: item for item in catalog_tests}
    results = []

    def convert(case: dict, raw: dict | None) -> dict:
        screenshot_meta = None
        if raw:
            image = decode_screenshot(raw.get("screenshot"))
            if image:
                width, height = png_size(image)
                relative = Path("screenshots") / emulator_id / run_id / f"{case['id']}.png"
                destination = output_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(image)
                screenshot_meta = {"url": relative.as_posix(), "width": width, "height": height}
        return result_record(case, raw, screenshot_meta)

    for case in catalog_tests:
        results.append(convert(case, raw_tests.get(case["legacyName"])))

    for name in sorted(set(raw_tests) - set(catalog_by_name)):
        results.append(convert(result_case_metadata(name, catalog_by_name), raw_tests[name]))

    recorded = [item for item in results if item["status"] in {"pass", "fail", "info"}]
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("pass", "fail", "info", "error", "skipped", "missing")
    }
    score = {"value": counts["pass"] + counts["info"], "recorded": len(recorded)}
    result_document = {
        "schemaVersion": SCHEMA_VERSION,
        "emulatorId": emulator_id,
        "runId": run_id,
        "runState": "legacy",
        "testedAt": tested_at,
        "emulatorVersion": None,
        "catalogId": catalog_id,
        "catalogUrl": f"data/catalogs/{catalog_id}.json",
        "provenance": {
            "runnerCommit": None,
            "workflowUrl": None,
            "platform": "windows",
            "selection": {"emulators": [emulator_id], "tests": None, "systems": None},
            "importedLegacy": True,
        },
        "counts": counts,
        "score": score,
        "results": results,
    }
    summary = {
        "testedAt": tested_at,
        "runId": run_id,
        "runState": "legacy",
        "catalogId": catalog_id,
        "counts": counts,
        "score": score,
        "coverage": {"recorded": len(recorded), "catalogTotal": len(catalog_tests)},
    }
    return result_document, summary


def copy_static_files(web_dir: Path, output_dir: Path) -> None:
    for name in STATIC_FILES:
        source = web_dir / name
        destination = output_dir / name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def build_site(
    *, emulators_path: Path, tests_path: Path, results_dir: Path, output_dir: Path, web_dir: Path
) -> dict:
    if output_dir.resolve() == results_dir.resolve():
        raise ValueError("output directory must be separate from the input results directory")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    copy_static_files(web_dir, output_dir)

    exported_emulators = read_json(emulators_path)
    catalog_tests = load_catalog_tests(tests_path)
    publish_reference_images(catalog_tests, output_dir)
    suites = [dict(suite) for suite in SUITES]
    catalog_id = catalog_id_for(catalog_tests, suites)
    catalog = {"schemaVersion": SCHEMA_VERSION, "id": catalog_id, "suites": suites, "tests": catalog_tests}
    write_json(output_dir / "data" / "catalogs" / f"{catalog_id}.json", catalog)

    summaries = []
    raw_dir = output_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(emulators_path, raw_dir / "emulators.json")
    shutil.copy2(tests_path, raw_dir / "tests.json")

    seen_ids = set()
    for display_name, exported in exported_emulators.items():
        metadata = EMULATORS.get(display_name)
        if metadata is None:
            raise ValueError(f"missing site metadata for emulator {display_name!r}")
        emulator_id = exported.get("id", metadata["id"])
        if emulator_id in seen_ids:
            raise ValueError(f"duplicate emulator ID: {emulator_id}")
        seen_ids.add(emulator_id)
        filename = validate_relative_filename(exported["file"])
        source_path = results_dir / filename

        if source_path.exists():
            source = read_json(source_path)
            result_document, derived = build_emulator_result(
                emulator_id=emulator_id,
                source=source,
                catalog_tests=catalog_tests,
                output_dir=output_dir,
                catalog_id=catalog_id,
            )
            write_json(output_dir / "data" / "results" / f"{emulator_id}.json", result_document)
            shutil.copy2(source_path, raw_dir / filename)
        else:
            derived = {
                "testedAt": None,
                "runId": None,
                "runState": "missing",
                "catalogId": catalog_id,
                "counts": {status: 0 for status in ("pass", "fail", "info", "error", "skipped", "missing")},
                "score": {"value": 0, "recorded": 0},
                "coverage": {"recorded": 0, "catalogTotal": len(catalog_tests)},
            }

        systems = exported.get("systems", metadata["systems"])
        summaries.append(
            {
                "id": emulator_id,
                "name": display_name,
                "homepage": exported["url"],
                "systems": systems,
                "version": None,
                "resultsUrl": f"data/results/{emulator_id}.json" if source_path.exists() else None,
                **derived,
            }
        )

    summaries.sort(key=lambda item: (-item["score"]["value"], item["name"].casefold()))
    index = {
        "schemaVersion": SCHEMA_VERSION,
        "publishedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scorePolicy": SCORE_POLICY,
        "emulators": summaries,
    }
    write_json(output_dir / "data" / "index.json", index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emulators", default="emulators.json")
    parser.add_argument("--tests", default="tests.json")
    parser.add_argument("--results-dir", default=".")
    parser.add_argument("--output-dir", default="site")
    parser.add_argument("--web-dir", default="web")
    args = parser.parse_args()

    index = build_site(
        emulators_path=Path(args.emulators),
        tests_path=Path(args.tests),
        results_dir=Path(args.results_dir),
        output_dir=Path(args.output_dir),
        web_dir=Path(args.web_dir),
    )
    total = sum(item["coverage"]["recorded"] for item in index["emulators"])
    print(f"Built {args.output_dir}: {len(index['emulators'])} emulators, {total} recorded results")


if __name__ == "__main__":
    main()
