#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成与 favicon.svg 同形的 256px PNG/ICO，无第三方依赖。"""
from pathlib import Path
import struct, zlib, math

OUT = Path(__file__).resolve().parent.parent / 'dgtf_app' / 'static' / 'dgtf.ico'
S = 512          # supersample
FINAL = 256
BG = (13, 17, 23)
GREEN = (126, 231, 135)
BLUE = (88, 166, 255)

def inside_rr(x, y, w, h, r):
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    cx = min(max(x, r), w - r)
    cy = min(max(y, r), h - r)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r

def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

poly64 = [(14,44),(14,20),(21,20),(31,34),(31,20),(38,20),(38,44),(32,44),(21,30),(21,44)]
scale = S / 64.0
poly = [(x * scale, y * scale) for x, y in poly64]
radius = 14 * scale
circle = (47 * scale, 32 * scale, 6 * scale)

# RGBA supersampled
pix = bytearray(S * S * 4)
for y in range(S):
    for x in range(S):
        i = (y * S + x) * 4
        if not inside_rr(x + 0.5, y + 0.5, S, S, radius):
            continue
        r, g, b = BG
        if point_in_poly(x + 0.5, y + 0.5, poly):
            r, g, b = GREEN
        else:
            dx = x + 0.5 - circle[0]; dy = y + 0.5 - circle[1]
            if dx * dx + dy * dy <= circle[2] * circle[2]:
                r, g, b = BLUE
        pix[i:i+4] = bytes((r, g, b, 255))

# box downsample
out = bytearray(FINAL * FINAL * 4)
for y in range(FINAL):
    for x in range(FINAL):
        rs = gs = bs = as_ = 0
        for yy in range(2):
            for xx in range(2):
                sx, sy = x * 2 + xx, y * 2 + yy
                i = (sy * S + sx) * 4
                rs += pix[i]; gs += pix[i+1]; bs += pix[i+2]; as_ += pix[i+3]
        o = (y * FINAL + x) * 4
        out[o:o+4] = bytes((rs//4, gs//4, bs//4, as_//4))

# PNG
def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
raw = b''.join(b'\x00' + bytes(out[y*FINAL*4:(y+1)*FINAL*4]) for y in range(FINAL))
png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', FINAL, FINAL, 8, 6, 0, 0, 0))
       + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
# ICO with one 256px PNG entry
ico = struct.pack('<HHH', 0, 1, 1)
ico += struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png), 22)
ico += png
OUT.write_bytes(ico)
print('WROTE', OUT, len(ico), 'bytes')
