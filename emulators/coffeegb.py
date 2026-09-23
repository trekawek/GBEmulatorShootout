import math
import os
import re
import subprocess
import tempfile
import time

import PIL.Image
import requests

from emulator import Emulator, TestResult
from test import *
from util import *


COFFEE_GB_LATEST_RELEASE = (
    "https://api.github.com/repos/trekawek/coffee-gb/releases/latest"
)
COFFEE_GB_MAVEN_BASE = (
    "https://repo.maven.apache.org/maven2/eu/rekawek/coffeegb/coffee-gb-cli"
)
COFFEE_GB_FPS = 60
COFFEE_GB_SETTLING_SECONDS = 5.0
COFFEE_GB_PRESENTATION_FRAMES = 1
COFFEE_GB_REQUEST_TIMEOUT = 60.0


class CoffeeGB(Emulator):
    def __init__(self):
        super().__init__(
            "Coffee GB",
            "https://github.com/trekawek/coffee-gb",
            startup_time=2.0,
            features=(PCM,),
        )
        self._cli_jar = None

    def setup(self):
        response = requests.get(COFFEE_GB_LATEST_RELEASE, timeout=30)
        response.raise_for_status()
        tag = response.json().get("tag_name", "")
        match = re.fullmatch(r"coffee-gb-([0-9A-Za-z][0-9A-Za-z._-]*)", tag)
        if match is None:
            raise RuntimeError("Unexpected Coffee GB release tag: %s" % tag)

        # Coffee GB publishes the official headless CLI to Maven Central before
        # making the corresponding GitHub release public.
        version = match.group(1)
        self._cli_jar = os.path.join(
            "downloads", "coffee-gb-cli-%s.jar" % version)
        download(
            "%s/%s/coffee-gb-cli-%s.jar"
            % (COFFEE_GB_MAVEN_BASE, version, version),
            self._cli_jar,
        )

    @staticmethod
    def _frames_for_runtime(runtime):
        # The generic GUI harness grants every emulator five extra seconds for a
        # result screen to settle. Reproduce that allowance as emulated time, then
        # present one more complete LCD frame so writes performed at the inclusive
        # deadline are visible in the captured image.
        return max(
            1,
            math.ceil((runtime + COFFEE_GB_SETTLING_SECONDS) * COFFEE_GB_FPS)
            + COFFEE_GB_PRESENTATION_FRAMES,
        )

    @staticmethod
    def _profile_for_test(test):
        if test.model != CGB:
            return test.model.lower()

        # Explicit CGB mode is still required for monochrome ROMs that the suite
        # deliberately runs on color hardware. Color-aware ROMs can use Coffee GB's
        # automatic profile so cartridge-specific revision selection is preserved.
        with open(test.rom, "rb") as rom:
            rom.seek(0x143)
            cgb_flag = rom.read(1)
        if len(cgb_flag) != 1:
            raise RuntimeError("Coffee GB test ROM has an incomplete header")
        return "auto" if cgb_flag[0] & 0x80 else "cgb"

    def run(self, test):
        print("Running %s on %s" % (test, self), flush=True)
        if self._cli_jar is None:
            raise RuntimeError("Coffee GB headless CLI is not available")

        sav_file = os.path.splitext(test.rom)[0] + ".sav"
        if os.path.exists(sav_file):
            os.unlink(sav_file)

        fd, screenshot_path = tempfile.mkstemp(suffix=".png", prefix="coffee-gb-")
        os.close(fd)
        os.unlink(screenshot_path)

        start_time = time.monotonic()
        try:
            try:
                completed = subprocess.run(
                    [
                        "java",
                        "-Djava.awt.headless=true",
                        "-jar", os.path.abspath(self._cli_jar),
                        "run",
                        "--rom", os.path.abspath(test.rom),
                        "--frames", str(self._frames_for_runtime(test.runtime)),
                        "--profile", self._profile_for_test(test),
                        "--bootstrap", "fast-forward",
                        "--sgb-border", "off",
                        "--screenshot", os.path.abspath(screenshot_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=COFFEE_GB_REQUEST_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                raise TimeoutError(
                    "Coffee GB exceeded %.0f seconds while running %s"
                    % (COFFEE_GB_REQUEST_TIMEOUT, test))
            if completed.returncode != 0:
                diagnostic = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(
                    "Coffee GB CLI failed with exit code %d: %s"
                    % (completed.returncode, diagnostic))

            with PIL.Image.open(screenshot_path) as image:
                screenshot = image.copy()
            result = test.checkResult(screenshot)
            if result is None:
                result = test.getDefaultResult()
            elapsed = time.monotonic() - start_time
            return TestResult(
                result=result,
                screenshot=screenshot,
                startuptime=0.0,
                runtime=elapsed,
            )
        finally:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
