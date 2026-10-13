"""Draw the app icon: the dashboard's ring logo (ICON.logo in healthaio/web/js/app.js) on the light page colour.

Python standard library only. Each pixel's coverage comes from its distance to the ring's strokes, which gives
smooth edges without supersampling. Run from anywhere:

    python3 ios/tools/make_icon.py
"""

import math
import struct
import zlib
from pathlib import Path

SIZE = 1024
OUT = Path(__file__).resolve().parent.parent / "HealthAIO" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon.png"

# Colours from healthaio/web/css/tokens.css (light mode).
BACKGROUND = (0xF4, 0xF4, 0xF3)
INK = (0x16, 0x16, 0x16)
BAND_ALPHA = 0.075  # --c-band: rgba(22, 22, 22, .075)
SLEEP = (0x4A, 0x3A, 0xA7)
FOCUS = (0x2A, 0x78, 0xD6)
FUN = (0xEB, 0x68, 0x34)

# The logo is drawn on a 32-unit box: radius 12.5, stroke 5, three arcs given by their end points.
LOGO_CENTER = 16.0
ARCS = [
    (SLEEP, (16.0, 3.5), (27.8, 11.8)),
    (FOCUS, (28.3, 18.5), (21.7, 27.6)),
    (FUN, (17.5, 28.4), (7.8, 24.7)),
]
RADIUS = 0.30 * SIZE
STROKE = RADIUS * 5.0 / 12.5


def angle_of(point):
    return math.atan2(point[1] - LOGO_CENTER, point[0] - LOGO_CENTER)


def arc_spec(start, end):
    a0, a1 = angle_of(start), angle_of(end)
    if a1 < a0:
        a1 += 2 * math.pi
    return a0, a1


SPECS = [(colour, *arc_spec(start, end)) for colour, start, end in ARCS]


def coverage(distance):
    return max(0.0, min(1.0, 0.5 - distance))


def arc_distance(x, y, r, angle, a0, a1):
    """Signed distance in pixels from (x, y) to a round-capped arc stroke (clockwise from a0 to a1)."""
    a = angle
    while a < a0:
        a += 2 * math.pi
    if a <= a1:
        return abs(r - RADIUS) - STROKE / 2
    best = float("inf")
    for edge in (a0, a1):
        cx = SIZE / 2 + RADIUS * math.cos(edge)
        cy = SIZE / 2 + RADIUS * math.sin(edge)
        best = min(best, math.hypot(x - cx, y - cy))
    return best - STROKE / 2


def mix(base, colour, alpha):
    return tuple(b + (c - b) * alpha for b, c in zip(base, colour))


def render():
    rows = []
    centre = SIZE / 2
    for j in range(SIZE):
        y = j + 0.5
        row = bytearray([0])  # PNG filter type 0
        for i in range(SIZE):
            x = i + 0.5
            dx, dy = x - centre, y - centre
            r = math.hypot(dx, dy)
            pixel = BACKGROUND
            # Round caps are discs centred on the ring line, so they never leave the band.
            band = coverage(abs(r - RADIUS) - STROKE / 2)
            if band > 0:
                pixel = mix(pixel, INK, BAND_ALPHA * band)
                angle = math.atan2(dy, dx)
                for colour, a0, a1 in SPECS:
                    cover = coverage(arc_distance(x, y, r, angle, a0, a1))
                    if cover > 0:
                        pixel = mix(pixel, colour, cover)
            row.extend(int(round(v)) for v in pixel)
        rows.append(bytes(row))
    return b"".join(rows)


def png(raw):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)  # 8-bit RGB, no alpha (iOS icons are opaque)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    OUT.write_bytes(png(render()))
    print(f"wrote {OUT.name} ({SIZE}x{SIZE})")
