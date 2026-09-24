from util import *
from emulator import Emulator
from test import *
import shutil
import os


class GameRoy(Emulator):
    def __init__(self, spec):
        super().__init__(spec.name, spec.url, startup_time=0.8, features=None)
        self.title_check = lambda title: title.endswith('gameroy')
        self.speed = 15.0

    def setup(self):
        downloadGithubRelease("Rodrigodd/gameroy", "downloads/gameroy.zip")
        extract("downloads/gameroy.zip", "emu/gameroy")
        setDPIScaling("emu/gameroy/gameroy.exe")

        setupMesa(r"emu\gameroy")
    
    def startProcess(self, rom, *, model, required_features):
        if model != DMG:
            return None
        return subprocess.Popen([
            "emu/gameroy/gameroy.exe",
            "--screen-size", "160x144",
            "--frame-skip",
            os.path.abspath(rom),
        ], cwd="emu/gameroy")
