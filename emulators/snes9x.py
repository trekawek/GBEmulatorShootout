import glob
import os
import subprocess

import PIL.Image

from emulator import Emulator
from test import CGB, DMG, PCM, SGB
from util import downloadGithubRelease, extract, getScreenshot, setDPIScaling


class SuperSnes9x(Emulator):
    def __init__(self):
        super().__init__(
            "SuperSnes9x",
            "https://github.com/shanytc/snes9x/releases",
            startup_time=1.0,
            features=(PCM,),
        )
        self.title_check = lambda title: "SuperSnes9x" in title

    def setup(self):
        archive_filename = "downloads/super-snes9x-windows.zip"
        downloadGithubRelease(
            "shanytc/snes9x",
            archive_filename,
            filter=lambda name: (
                name.startswith("super-snes9x-")
                and name.endswith("-win32-x64.zip")
            ),
            require_asset=True,
        )
        extract(archive_filename, "emu/snes9x")

        executables = glob.glob(
            os.path.join("emu", "snes9x", "**", "super-snes9x-x64.exe"),
            recursive=True,
        )
        if not executables:
            raise FileNotFoundError(
                "Could not locate the SuperSnes9x executable after setup"
            )
        self.executable = executables[0]
        self.path = os.path.dirname(self.executable)
        setDPIScaling(self.executable)

    def startProcess(self, rom, *, model, required_features):
        # SuperSnes9x needs an external, copyrighted SGB/SGB2 BIOS for true
        # Super Game Boy mode. The release does not include one.
        if model == SGB:
            return None

        config_name = {
            DMG: "snes9x.dmg.conf",
            CGB: "snes9x.gbc.conf",
        }.get(model)
        if config_name is None:
            return None

        config = os.path.abspath(
            os.path.join(os.path.dirname(__file__), config_name)
        )
        return subprocess.Popen(
            [
                os.path.abspath(self.executable),
                "-nostdconf",
                "-conf",
                config,
                "-hidemenu",
                os.path.abspath(rom),
            ],
            cwd=self.path,
        )

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None

        # Stable releases use one saved window size for both SNES and GB
        # content, so remove any letterboxing before normalizing the image.
        width, height = screenshot.size
        target_ratio = 160 / 144
        if width / height > target_ratio:
            cropped_width = round(height * target_ratio)
            left = (width - cropped_width) // 2
            screenshot = screenshot.crop((left, 0, left + cropped_width, height))
        elif width / height < target_ratio:
            cropped_height = round(width / target_ratio)
            top = (height - cropped_height) // 2
            screenshot = screenshot.crop((0, top, width, top + cropped_height))

        return screenshot.resize((160, 144), PIL.Image.NEAREST)
