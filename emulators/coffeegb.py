import base64
import math
import os
import queue
import tempfile
import threading
import time

from emulator import Emulator, TestResult
from test import *
from util import *


COFFEE_GB_VERSION = "2.1.6"
COFFEE_GB_JAR = os.path.join("downloads", "coffee-gb-%s.jar" % COFFEE_GB_VERSION)
COFFEE_GB_URL = (
    "https://github.com/trekawek/coffee-gb/releases/download/"
    "coffee-gb-%s/coffee-gb-%s.jar" % (COFFEE_GB_VERSION, COFFEE_GB_VERSION)
)
COFFEE_GB_HEADLESS_SOURCE = os.path.join("emulators", "CoffeeGbHeadless.java")
COFFEE_GB_HEADLESS_CLASSES = os.path.join("emu", "coffee-gb", "headless")
COFFEE_GB_FPS = 60
COFFEE_GB_SETTLING_SECONDS = 5.0
COFFEE_GB_REQUEST_TIMEOUT = 60.0


class CoffeeGB(Emulator):
    def __init__(self):
        super().__init__(
            "Coffee GB",
            "https://github.com/trekawek/coffee-gb",
            startup_time=2.0,
            features=(PCM,),
        )
        self._headless = None
        self._responses = queue.Queue()
        self._request_id = 0

    def setup(self):
        download(COFFEE_GB_URL, COFFEE_GB_JAR)
        os.makedirs(COFFEE_GB_HEADLESS_CLASSES, exist_ok=True)
        subprocess.run([
            "javac",
            "-cp", os.path.abspath(COFFEE_GB_JAR),
            "-d", os.path.abspath(COFFEE_GB_HEADLESS_CLASSES),
            os.path.abspath(COFFEE_GB_HEADLESS_SOURCE),
        ], check=True)
        self._headless = subprocess.Popen(
            [
                "java",
                "-Djava.awt.headless=true",
                "-cp", os.pathsep.join([
                    os.path.abspath(COFFEE_GB_HEADLESS_CLASSES),
                    os.path.abspath(COFFEE_GB_JAR),
                ]),
                "CoffeeGbHeadless",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready = self._headless.stdout.readline().strip()
        if ready != "READY":
            raise RuntimeError("Coffee GB headless runner failed to start: %s" % ready)
        threading.Thread(target=self._read_responses, daemon=True).start()

    def _read_responses(self):
        for line in self._headless.stdout:
            self._responses.put(line.rstrip("\r\n"))

    @staticmethod
    def _encode_path(path):
        return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")

    @staticmethod
    def _frames_for_runtime(runtime):
        # The generic GUI harness grants every emulator five extra seconds for a
        # result screen to settle. Reproduce that allowance as emulated time.
        return max(1, math.ceil((runtime + COFFEE_GB_SETTLING_SECONDS) * COFFEE_GB_FPS))

    def run(self, test):
        print("Running %s on %s" % (test, self), flush=True)
        if self._headless is None or self._headless.poll() is not None:
            raise RuntimeError("Coffee GB headless runner is not available")

        sav_file = os.path.splitext(test.rom)[0] + ".sav"
        if os.path.exists(sav_file):
            os.unlink(sav_file)

        self._request_id += 1
        request_id = str(self._request_id)
        fd, screenshot_path = tempfile.mkstemp(
            suffix=".png", prefix="coffee-gb-", dir=COFFEE_GB_HEADLESS_CLASSES)
        os.close(fd)
        os.unlink(screenshot_path)
        request = "\t".join([
            request_id,
            self._encode_path(os.path.abspath(test.rom)),
            test.model.lower(),
            str(self._frames_for_runtime(test.runtime)),
            self._encode_path(os.path.abspath(screenshot_path)),
        ])

        start_time = time.monotonic()
        try:
            self._headless.stdin.write(request + "\n")
            self._headless.stdin.flush()
            try:
                response = self._responses.get(timeout=COFFEE_GB_REQUEST_TIMEOUT)
            except queue.Empty:
                self._headless.kill()
                raise TimeoutError(
                    "Coffee GB exceeded %.0f seconds while running %s"
                    % (COFFEE_GB_REQUEST_TIMEOUT, test))
            fields = response.split("\t")
            if len(fields) < 2 or fields[1] != request_id:
                raise RuntimeError("Unexpected Coffee GB response: %s" % response)
            if fields[0] != "OK":
                message = "Unknown Coffee GB failure"
                if len(fields) >= 3:
                    message = base64.urlsafe_b64decode(fields[2] + "===").decode("utf-8")
                raise RuntimeError(message)

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

    def undoSetup(self):
        if self._headless is None:
            return
        if self._headless.poll() is None:
            try:
                self._headless.stdin.write("QUIT\n")
                self._headless.stdin.flush()
                self._headless.wait(timeout=10.0)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self._headless.kill()
                self._headless.wait()
        self._headless = None

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
                    "system.bootstrapMode=FAST_FORWARD",
                ])
            )

        return subprocess.Popen([
            "java",
            "-Dsun.java2d.uiScale=1",
            "-Duser.home=%s" % home,
            "-jar",
            os.path.abspath(COFFEE_GB_JAR),
            os.path.abspath(rom),
        ], cwd=home)

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None or screenshot.size[0] < 160 or screenshot.size[1] < 144:
            return None
        return screenshot.crop((0, screenshot.size[1] - 144, 160, screenshot.size[1]))
