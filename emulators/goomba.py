from util import *
from emulator import Emulator
import shutil
import requests
import re
import time


class Goomba(Emulator):
    def __init__(self, spec):
        super().__init__(spec.name, spec.url, startup_time=1.0)
        self.title_check = lambda title: "mGBA" in title
    
    def setup(self):
        res = requests.get("https://www.dwedit.org/gba/goombacolor.php")
        url = re.search("<a href=\"([^\"]+)\">Download</a>", res.text).group(1)
        download("https://www.dwedit.org/gba/" + url, "downloads/goomba.zip")
        extract("downloads/goomba.zip", "emu/goomba")

        download("https://s3.amazonaws.com/mgba/mGBA-build-latest-win64.7z", "downloads/mgba.7z")
        extract("downloads/mgba.7z", "emu/mgba")
        self.path = os.path.join("emu", "mgba", os.listdir("emu/mgba")[0])
        setDPIScaling("%s/mGBA.exe" % (self.path))
        setDPIScaling("%s/mgba-sdl.exe" % (self.path))
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mgba.qt.ini"), "%s/qt.ini" % (self.path))
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mgba.config.ini"), "%s/config.ini" % (self.path))

    def startProcess(self, rom, *, model, required_features):
        gba_rom = "emu/goomba/goomba.gba.rom.gba"
        try:
            f = open(gba_rom, "wb")
        except OSError:
            time.sleep(0.1)
            f = open(gba_rom, "wb")
        f.write(open("emu/goomba/goomba.gba", "rb").read())
        f.write(open(rom, "rb").read())
        f.close()
    
        env = {"SDL_RENDER_DRIVER": "software"}
        for k, v in os.environ.items():
            env[k] = v
        return subprocess.Popen(["%s/mgba-sdl.exe" % (self.path), os.path.abspath(gba_rom)], cwd=self.path, env=env)

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None
        x = (screenshot.size[0] - 160) // 2
        y = (screenshot.size[1] - 144) // 2
        screenshot = screenshot.crop((x, y, x + 160, y + 144))
        return screenshot
