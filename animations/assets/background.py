"""Tween the camera's background colour — the one way a scene here changes it.

    self.play(bg_to(self, BOARD_NAVY), ..., run_time=1.5)

Promoted from scene 01's `_bg_to` when scene 10 became the second scene to need it.
The camera's `background_color` setter rebuilds the background, so a tween is an
alpha function setting it every frame; the Mobject it hangs on is a dummy.
"""
from config import *


def bg_to(scene, color):
    """An animation taking the camera background from its current colour to `color`."""
    cam, c0 = scene.camera, ManimColor(scene.camera.background_color)
    return UpdateFromAlphaFunc(
        Mobject(), lambda m, a: setattr(cam, "background_color",
                                        interpolate_color(c0, color, a)))
