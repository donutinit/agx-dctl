#!/usr/bin/env python3
"""Renderiza una imagen de prueba con el DCTL compilado en CPU y la guarda en PNG.

La imagen va en DaVinci Intermediate / DWG, como la recibiria el DCTL en Resolve:
arriba una rampa de grises, abajo un barrido de tonos (vertical) por exposicion
(horizontal, de -10 a +8 EV respecto a gris medio).

Uso: render.py <salida.png> [p_control=valor ...]
"""
import array
import math
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from run import BUILD, D65, DWG, REC2020, hue_rgb, inv3, lin_to_di, mat_vec, npm

W, H = 960, 540


def png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    out = sys.argv[1]
    controls = dict(a.split("=") for a in sys.argv[2:])
    subprocess.run(["make", "-s", "-C", str(BUILD.parent)], check=True)

    npm_dwg = npm(DWG, D65)
    to_dwg = [[sum(inv3(npm_dwg)[r][k] * npm(REC2020, D65)[k][c] for k in range(3)) for c in range(3)]
              for r in range(3)]
    px = array.array("f")
    for y in range(H):
        for x in range(W):
            ev = -10.0 + 18.0 * x / (W - 1)
            v = 0.18 * 2 ** ev
            if y < H // 8:
                rgb = (v, v, v)
            else:
                hue = 360.0 * (y - H // 8) / (H - H // 8)
                rgb = tuple(v * (0.1 + 0.9 * k) for k in hue_rgb(hue))
            px.extend(lin_to_di(c) for c in mat_vec(to_dwg, rgb))

    with tempfile.TemporaryDirectory(dir=BUILD) as tmp:
        tmp = Path(tmp)
        px.tofile(open(tmp / "in.f32", "wb"))
        (tmp / "p.txt").write_text("".join(f"{k} {v}\n" for k, v in controls.items()))
        subprocess.run([str(BUILD / "dctl_run"), str(tmp / "p.txt"), str(tmp / "in.f32"), str(tmp / "out.f32"),
                        str(W), str(H)], check=True)
        res = array.array("f")
        res.frombytes((tmp / "out.f32").read_bytes())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    png(out, W, H, [max(0, min(255, round(c * 255))) if not math.isnan(c) else 0 for c in res])


if __name__ == "__main__":
    main()
