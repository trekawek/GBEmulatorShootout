import base64
import json
import tempfile
import unittest
from pathlib import Path

from build import build_site
from site_metadata import current_test_metadata


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
).decode("ascii")


class StaticSiteBuildTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results = self.root / "results"
        self.results.mkdir()
        self.output = self.root / "site"
        self.emulators = self.root / "emulators.json"
        self.tests = self.root / "tests.json"

        self.emulators.write_text(
            json.dumps(
                {
                    "SameBoy": {
                        "file": "sameboy.json",
                        "url": "https://sameboy.github.io/",
                    }
                }
            ),
            encoding="utf-8",
        )
        self.tests.write_text(
            json.dumps(
                [
                    {
                        "id": "acid-dmg-acid2-dmg-test",
                        "legacyName": "acid/dmg-acid2.gb",
                        "name": "dmg-acid2.gb",
                        "suiteId": "acid",
                        "group": "",
                        "system": "dmg",
                        "requiredFeatures": [],
                        "description": "Rendering test",
                        "sourceUrl": "https://github.com/mattcurrie/dmg-acid2",
                    }
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def write_result(self, status="INFO"):
        (self.results / "sameboy.json").write_text(
            json.dumps(
                {
                    "emulator": "SameBoy",
                    "date": 1_700_000_000,
                    "tests": {
                        "acid/dmg-acid2.gb": {
                            "result": status,
                            "startuptime": 0.5,
                            "runtime": 1.5,
                            "screenshot": PNG_1X1,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def build(self):
        return build_site(
            emulators_path=self.emulators,
            tests_path=self.tests,
            results_dir=self.results,
            output_dir=self.output,
            web_dir=Path(__file__).parent / "web",
        )

    def test_decodes_screenshot_and_preserves_legacy_score(self):
        self.write_result()
        index = self.build()
        summary = index["emulators"][0]
        self.assertEqual({"value": 1, "recorded": 1}, summary["score"])
        self.assertEqual(1, summary["counts"]["info"])

        result = json.loads((self.output / summary["resultsUrl"]).read_text(encoding="utf-8"))
        record = result["results"][0]
        self.assertEqual("info", record["status"])
        image_path = self.output / record["screenshot"]["url"]
        self.assertEqual((1, 1), (record["screenshot"]["width"], record["screenshot"]["height"]))
        self.assertTrue(image_path.is_file())
        self.assertNotIn("screenshot", (self.output / "data" / "index.json").read_text(encoding="utf-8"))

        catalog = json.loads((self.output / result["catalogUrl"]).read_text(encoding="utf-8"))
        reference = catalog["tests"][0]["expected"][0]
        self.assertTrue((self.output / reference["url"]).is_file())
        self.assertGreater(reference["width"], 0)
        self.assertNotIn("expectedPaths", catalog["tests"][0])

    def test_publishes_every_accepted_reference_variant(self):
        case = next(
            item for item in current_test_metadata()
            if item["legacyName"] == "daid/ppu_scanline_bgp.gb (DMG)"
        )
        self.tests.write_text(json.dumps([case]), encoding="utf-8")
        self.build()

        catalog_path = next((self.output / "data" / "catalogs").glob("*.json"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        references = catalog["tests"][0]["expected"]
        self.assertEqual(3, len(references))
        self.assertEqual(3, len({item["url"] for item in references}))
        self.assertTrue(all((self.output / item["url"]).is_file() for item in references))

    def test_rejects_unknown_legacy_status(self):
        self.write_result(status="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "unexpected legacy status"):
            self.build()


if __name__ == "__main__":
    unittest.main()
