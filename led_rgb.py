# RGB Matrix Driver for Waveshare LED RGB Matrix
# ruff: noqa: F821
import array
import math
import time

import rp2
from machine import Pin


# WS2812 PIO program
@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24,
)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1).side(0)[T3 - 1]
    jmp(not_x, "do_zero").side(1)[T1 - 1]
    jmp("bitloop").side(1)[T2 - 1]
    label("do_zero")
    nop().side(0)[T2 - 1]
    wrap()


# 5x10 numeric only font, including '-', '+', ':', ')', '('
FONT = {
    "0": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "1": [0x01, 0x03, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01],
    "2": [0x0E, 0x11, 0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10, 0x1F],
    "3": [0x0E, 0x11, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x01, 0x11, 0x0E],
    "4": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x01, 0x01],
    "5": [0x1F, 0x10, 0x10, 0x10, 0x1E, 0x01, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x0E, 0x11, 0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x11, 0x0E],
    "-": [0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00],
    "+": [0x00, 0x00, 0x00, 0x02, 0x07, 0x02, 0x00, 0x00, 0x00, 0x00],
    ":": [0x00, 0x00, 0x06, 0x06, 0x00, 0x00, 0x06, 0x06, 0x00, 0x00],
    ")": [0x00, 0x18, 0x04, 0x02, 0x02, 0x02, 0x02, 0x04, 0x18, 0x00],
    "(": [0x03, 0x04, 0x04, 0x08, 0x08, 0x08, 0x08, 0x04, 0x04, 0x03],
}


ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2


class Matrix:
    def __init__(self, pin=6, width=16, height=10):
        self.width = width
        self.height = height

        self.sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(pin))
        self.sm.active(1)

        self.ar = array.array("I", [0 for _ in range(width * height)])

        # These are some distinctive colors of low intence I've found usable
        self.RED = (1, 0, 0)
        self.GREEN = (0, 1, 0)
        self.BLUE = (0, 0, 1)
        self.YELLOW = (1, 1, 0)
        self.ORANGE = (3, 1, 0)
        self.AZURE = (0, 1, 1)
        self.MAGENTA = (1, 0, 1)
        self.VIOLET = (1, 0, 2)
        self.WHITE = (1, 1, 1)
        self.CYAN = (0, 1, 2)
        self.BLACK = (0, 0, 0)

    def __setitem__(self, i, color):
        if i >= 0 and i < self.width * self.height:
            r, g, b = color
            self.ar[i] = (g << 8) | (r << 16) | b

    def set_xy(self, x, y, color):
        self[self.width * y + x] = color

    def fill(self, color):
        for i in range(self.width * self.height):
            self[i] = color

    def clear(self):
        self.fill(self.BLACK)

    def glyph_width(self, glyph):
        return max(len(bin(x)) - 2 for x in glyph)

    def draw_glyph(self, glyph, x, color):
        w = self.glyph_width(glyph)
        for y, row in enumerate(glyph):
            if x >= 0:
                offset = y * self.width + x
                for bit in range(w):
                    on = (row >> ((w - 1) - bit)) & 1
                    if on:
                        self[offset] = color
                    offset += 1

    def can_render(self, value):
        if not isinstance(value, str) and not isinstance(value, int):
            return False

        return all(c in FONT for c in str(value))

    def draw_value(self, v, color, align=ALIGN_CENTER, show_sign=False):
        if not self.can_render(v):
            raise AttributeError(f"value can not be rendered: '{str(n)}'!")

        if isinstance(v, int) and show_sign and v >= 0:
            s = f"+{str(v)}"
        else:
            s = str(v)

        total_width = sum(self.glyph_width(FONT[c]) for c in s) + (len(str(s)) - 1)
        if align == ALIGN_RIGHT:
            x = self.width - total_width
        elif align == ALIGN_LEFT:
            x = 0
        else:
            if self.width - total_width < 0:
                x = self.width - total_width
            else:
                x = math.ceil((self.width - total_width) / 2)

        for c in s:
            self.draw_glyph(FONT[c], x, color)
            x += self.glyph_width(FONT[c]) + 1

    def write(self):
        for grb in self.ar:
            self.sm.put(grb, 8)
        time.sleep(0.01)


if __name__ == "__main__":
    print("testing matrix")
    m = Matrix()
    m.clear()
    m.draw_value("49", m.RED, align=ALIGN_CENTER, show_sign=True)
    m.write()
    time.sleep(5)

    m.clear()
    m.write()
