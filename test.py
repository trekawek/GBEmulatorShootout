import PIL.Image
import os

from util import *

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"

# Models
DMG = "DMG"
CGB = "CGB"
SGB = "SGB"

# Features
PCM = "PCM"

class Test:
    def __init__(self, name, *, runtime, rom=None, result=None, model=DMG, required_features=None, description=None, url=None, tags=None):
        rom = rom or name
        self.name = name
        self.rom = os.path.join("testroms", rom)
        self.model = model
        self.runtime = runtime
        self.description = description
        self.url = url
        self.tags = tags or set()
        self.required_features = required_features or set()

        assert os.path.exists(self.rom)
        if result is None:
            result = os.path.splitext(rom)[0] + ".png"
        if isinstance(result, list):
            result = [os.path.join("testroms", r) for r in result]
        else:
            result = [os.path.join("testroms", result)]
        self.expected_paths = [filename for filename in result if os.path.isfile(filename)]
        
        def tryOpenImage(filename):
            if filename is not None and os.path.exists(filename):
                return PIL.Image.open(filename)
            return None
        self.pass_result_filename = result[0]
        self.pass_result = [tryOpenImage(r) for r in result]
        self.fail_result = [tryOpenImage(os.path.splitext(r)[0] + ".fail.png") for r in result]
        self.pass_result = [img for img in self.pass_result if img]
        self.fail_result = [img for img in self.fail_result if img]

    def checkResult(self, screenshot):
        if self.pass_result is not None:
            for r in self.pass_result:
                if compareImage(screenshot, r):
                    return PASS
        if self.fail_result is not None:
            for r in self.fail_result:
                if compareImage(screenshot, r):
                    return FAIL
        return None

    def getDefaultResult(self):
        if self.pass_result:
            return FAIL
        return INFO

    def __repr__(self):
        return self.name
