import os

from emulator import Emulator
from test import *
from util import *


class CoffeeGB(Emulator):
    def __init__(self):
        super().__init__(
            "Coffee GB",
            "https://github.com/trekawek/coffee-gb",
            startup_time=2.0,
            features=(PCM,),
        )

    def setup(self):
        downloadGithubRelease(
            "trekawek/coffee-gb",
            "downloads/coffee-gb.jar",
            filter=lambda name: name.startswith("coffee-gb-") and name.endswith(".jar"),
            require_asset=True,
        )

    def startProcess(self, rom, *, model, required_features):
        model = {DMG: "DMG", CGB: "CGB", SGB: "SGB"}.get(model)
        if model is None:
            return None

        home = os.path.abspath(os.path.join("emu", "coffee-gb", model.lower()))
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, ".coffeegb.properties"), "wt") as f:
            f.write(
                "\n".join([
                    "system.dmgGames=%s" % model,
                    "system.cgbGames=%s" % model,
                    "display.scale=1",
                    "display.grayscale=false",
                    "display.blending=false",
                    "display.colorCorrection=false",
                    "display.rotation=0",
                    "display.showSgbBorder=false",
                    "sound.enabled=false",
                ])
            )

        return subprocess.Popen([
            "java",
            "-Dsun.java2d.uiScale=1",
            "-Duser.home=%s" % home,
            "-jar",
            os.path.abspath("downloads/coffee-gb.jar"),
            os.path.abspath(rom),
        ], cwd=home)

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None or screenshot.size[0] < 160 or screenshot.size[1] < 144:
            return None
        return screenshot.crop((0, screenshot.size[1] - 144, 160, screenshot.size[1]))
