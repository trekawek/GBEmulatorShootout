from util import *
from emulator import Emulator
from test import *
import shutil


class BGB(Emulator):
    def __init__(self, spec):
        super().__init__(spec.name, spec.url, startup_time=0.6, features=(PCM,))
        self.speed = 10.0

    def setup(self):
        download("https://bgb.bircd.org/bgb.zip", "downloads/bgb.zip")
        extract("downloads/bgb.zip", "emu/bgb")
        setDPIScaling("emu/bgb/bgb.exe")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "bgb.ini"), "emu/bgb/bgb.ini")
    
    def startProcess(self, rom, *, model, required_features):
        systemmode = {DMG: 0, CGB: 1, SGB: 2}.get(model)
        if systemmode is None:
            return None
        return subprocess.Popen(["emu/bgb/bgb.exe", "-set", "SystemMode=%d" % (systemmode), "-set", "Speed=%g" % (self.speed), "-set", "LoadRomWarnings=0", "-set", "Width=160", "-set", "detectgba=1", "-set", "Height=144", "-set", "SoundOut=null", os.path.abspath(rom)], cwd="emu/bgb")

