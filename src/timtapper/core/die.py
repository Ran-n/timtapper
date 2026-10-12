#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 16:53:25.421684
Revised: 2026/10/12 16:53:25.421684

Die faces: where the pips sit, shared by the app's die badges (ui.widgets) and the share cards
(share.render), so a die looks the same on screen and in a shared image.
"""

# Pip centres for each die face, as fractions of the face's side (standard layouts).
DIE_PIPS: dict[int, tuple[tuple[float, float], ...]] = {
    1: ((0.5, 0.5),),
    2: ((0.28, 0.28), (0.72, 0.72)),
    3: ((0.28, 0.28), (0.5, 0.5), (0.72, 0.72)),
    4: ((0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)),
    5: ((0.28, 0.28), (0.72, 0.28), (0.5, 0.5), (0.28, 0.72), (0.72, 0.72)),
    6: ((0.28, 0.25), (0.28, 0.5), (0.28, 0.75), (0.72, 0.25), (0.72, 0.5), (0.72, 0.75)),
}
# what a die badge shows for the roll: six pips when you won it, one when you lost it
WON_PIPS, LOST_PIPS = 6, 1
PIP_DIAMETER = 0.2  # of the face's side
CORNER_RADIUS = 0.22  # of the face's side
