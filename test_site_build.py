import base64
import json
import tempfile
import unittest
from pathlib import Path

from build import build_site


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

    def test_rejects_unknown_legacy_status(self):
        self.write_result(status="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "unexpected legacy status"):
            self.build()


if __name__ == "__main__":
    unittest.main()
