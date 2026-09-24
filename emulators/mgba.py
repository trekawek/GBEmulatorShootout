from util import *
from emulator import Emulator
from test import *
import shutil
import os


class MGBA(Emulator):
    def __init__(self, spec):
        super().__init__(spec.name, spec.url, startup_time=2.5, features=(PCM,))
        self.speed = 1.0

    def setup(self):
        # downloadGithubRelease("mgba-emu/mgba", "downloads/mgba.7z", filter=lambda n: "win32" in n and n.endswith(".7z"))
        download("https://s3.amazonaws.com/mgba/mGBA-build-latest-win64.7z", "downloads/mgba.7z")
        extract("downloads/mgba.7z", "emu/mgba")
        self.path = os.path.join("emu", "mgba", os.listdir("emu/mgba")[0])
        setDPIScaling("%s/mGBA.exe" % (self.path))
        setDPIScaling("%s/mgba-sdl.exe" % (self.path))
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mgba.qt.ini"), "%s/qt.ini" % (self.path))
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mgba.config.ini"), "%s/config.ini" % (self.path))

        setupMesa(self.path)
    
    def startProcess(self, rom, *, model, required_features):
        #return subprocess.Popen(["%s/mGBA.exe" % (self.path), os.path.abspath(rom)], cwd=self.path)
        env = {"SDL_RENDER_DRIVER": "software"}
        for k, v in os.environ.items():
            env[k] = v
        model = {DMG: "DMG", CGB: "CGB", SGB: "SGB"}.get(model)
        if model is None:
            return None
        return subprocess.Popen(["%s/mgba-sdl.exe" % (self.path), "-C", "gb.model=%s" % (model), "-C", "cgb.model=%s" % (model), "-C", "sgb.model=%s" % (model), os.path.abspath(rom)], cwd=self.path, env=env)

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None
        if screenshot.size[0] == 256: # SGB
            screenshot.crop((48, screenshot.size[1] - 144 - 40, 160, 144)).save("tmp.png")
            return screenshot.crop((48, screenshot.size[1] - 144 - 40, 160 + 48, screenshot.size[1] - 40))
        return screenshot.crop((0, screenshot.size[1] - 144, 160, screenshot.size[1]))
