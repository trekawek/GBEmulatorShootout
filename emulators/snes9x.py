import glob
import os
import subprocess

import PIL.Image

from emulator import Emulator
from test import CGB, DMG, PCM, SGB
from util import download, downloadGithubRelease, extract, getScreenshot, setDPIScaling


class SuperSnes9x(Emulator):
    def __init__(self, spec):
        super().__init__(
            spec.name,
            spec.url,
            startup_time=1.0,
            features=(PCM,),
        )
        self.title_check = lambda title: self.name in title
        self.sgb = False

    def setup(self):
        archive_filename = "downloads/super-snes9x-nightly-windows.zip"
        downloadGithubRelease(
            "shanytc/snes9x",
            archive_filename,
            filter=lambda name: name == "super-snes9x-nightly-win32-x64.zip",
            require_asset=True,
            release_tag="nightly",
        )
        extract(archive_filename, "emu/snes9x-nightly")

        executables = glob.glob(
            os.path.join(
                "emu", "snes9x-nightly", "**", "super-snes9x-x64.exe"
            ),
            recursive=True,
        )
        if not executables:
            raise FileNotFoundError(
                "Could not locate the SuperSnes9x executable after setup"
            )
        self.executable = executables[0]
        self.path = os.path.dirname(self.executable)
        setDPIScaling(self.executable)
        # SGB mode also runs the SNES-side cartridge image.
        download(
            "https://raw.githubusercontent.com/interface/retroarch_system/"
            "5f96368f6dbad5851cdb16a5041fefec4bdcd305/"
            "Nintendo%20-%20Super%20Game%20Boy/SGB1.sfc",
            os.path.join(self.path, "SGB1.sfc"),
        )
        download(
            "https://gbdev.gg8.se/files/roms/bootroms/sgb_boot.bin",
            os.path.join(self.path, "sgb_boot.bin"),
        )
        template = os.path.join(os.path.dirname(__file__), "snes9x.sgb.conf")
        self.sgb_config = os.path.abspath(os.path.join(self.path, "snes9x.sgb.conf"))
        with open(template, encoding="utf-8") as source:
            config = source.read().format(
                sgb1_bios=os.path.abspath(os.path.join(self.path, "SGB1.sfc")),
                sgb1_boot_rom=os.path.abspath(os.path.join(self.path, "sgb_boot.bin")),
            )
        with open(self.sgb_config, "w", encoding="utf-8") as target:
            target.write(config)

    def startProcess(self, rom, *, model, required_features):
        config_name = {
            DMG: "snes9x.dmg.conf",
            CGB: "snes9x.gbc.conf",
            SGB: "snes9x.sgb.conf",
        }.get(model)
        if config_name is None:
            return None
        self.sgb = model == SGB
        self.startup_time = 10.0 if self.sgb else 1.0

        config = (
            self.sgb_config
            if model == SGB
            else os.path.abspath(os.path.join(os.path.dirname(__file__), config_name))
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

        if self.sgb:
            # The SGB BIOS draws the GB picture at (48, 40) in the SNES
            # frame; the configured window keeps that area at native size.
            return screenshot.crop((48, 40, 208, 184))

        # SuperSnes9x uses one saved window size for both SNES and GB content,
        # so remove any letterboxing before normalizing the image.
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
