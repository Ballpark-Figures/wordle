from bpkfigures.scene import *


class WordleScene(BpkScene):
    def construct(self):
        self.camera.background_color = BG_COLOR
        super().construct()
