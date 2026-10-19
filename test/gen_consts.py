#!/usr/bin/env python3
"""Escribe en el DCTL las constantes que salen de darktable y de las especificaciones.

- Perfiles base (primarios y blanco en D50, matrices): de build/dtref consts, o sea
  de lcms2 y el codigo de darktable, igual que en darktable.
- Presets: de build/dtref preset <nombre>.
- DWG a Rec2020: de los primarios publicados por Blackmagic, en doble precision.

Uso: gen_consts.py [--check]   (--check no escribe; sale con 1 si el DCTL no esta al dia)
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DCTL = HERE.parent / "AgX_darktable.dctl"
DTREF = HERE / "build" / "dtref"
BEGIN = "// >>> generado por test/gen_consts.py: no editar a mano\n"
END = "// <<< generado\n"

# orden de agx_profile y del combo "base primaries" del DCTL
BASES = ["rec2020", "p3", "adobe", "srgb"]
# indice del DCTL para cada valor del enum dt_iop_agx_base_primaries_t:
# export profile (sRGB por defecto), working profile (Rec2020 por defecto), Rec2020, P3, Adobe, sRGB
DT_BASE_TO_DCTL = {0: 3, 1: 0, 2: 0, 3: 1, 4: 2, 5: 3}

PRESETS = ["scene-referred-default", "blender-like-base", "blender-like-punchy", "sigmoid-like-default",
           "sigmoid-like-smooth", "smooth", "unmodified-base-primaries"]

INT_FIELDS = {"auto_gamma", "base_primaries", "disable_primaries_adjustments", "completely_reverse_primaries"}

DWG = [(0.8000, 0.3130), (0.1682, 0.9877), (0.0790, -0.1155)]
REC2020 = [(0.708, 0.292), (0.170, 0.797), (0.131, 0.046)]
D65 = (0.3127, 0.3290)


def f(x):
    s = "%.9g" % x
    if "e" not in s and "." not in s and "n" not in s:
        s += ".0"
    return s + "f"


def inv3(m):
    a, b, c = m[0]
    d, e, g = m[1]
    h, i, j = m[2]
    det = a * (e * j - g * i) - b * (d * j - g * h) + c * (d * i - e * h)
    return [[(e * j - g * i) / det, (c * i - b * j) / det, (b * g - c * e) / det],
            [(g * h - d * j) / det, (a * j - c * h) / det, (c * d - a * g) / det],
            [(d * i - e * h) / det, (b * h - a * i) / det, (a * e - b * d) / det]]


def mul3(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def npm(primaries, white):
    p = [[x / y for x, y in primaries], [1.0, 1.0, 1.0], [(1 - x - y) / y for x, y in primaries]]
    w = [white[0] / white[1], 1.0, (1 - white[0] - white[1]) / white[1]]
    pi = inv3(p)
    s = [sum(pi[r][k] * w[k] for k in range(3)) for r in range(3)]
    return [[p[r][c] * s[c] for c in range(3)] for r in range(3)]


def mat_make(values, indent):
    rows = [", ".join(f(v) for v in values[i:i + 3]) for i in (0, 3, 6)]
    return "agx_mat_make(" + (",\n" + " " * (indent + 13)).join(rows) + ")"


def transposed(m):
    return [m[r][c] for c in range(3) for r in range(3)]


def dtref(*args):
    return subprocess.run([str(DTREF), *args], check=True, capture_output=True, text=True).stdout


def profiles_block():
    data = {}
    for line in dtref("consts").splitlines():
        name, key, *vals = line.split()
        data.setdefault(name, {})[key] = [float(v) for v in vals]

    out = ["// Perfiles base como los arma darktable (lcms2, primarios adaptados a D50).",
           "// 0 Rec2020, 1 Display P3, 2 Adobe RGB, 3 sRGB",
           "__DEVICE__ agx_profile agx_base_profile(int base)",
           "{",
           "  agx_profile p;"]
    # Rec2020 al final, como caso por defecto
    for n, idx in enumerate([1, 2, 3, 0]):
        d = data[BASES[idx]]
        out.append("  if(base == %d)" % idx if n == 0 else ("  else if(base == %d)" % idx if idx else "  else"))
        out.append("  {")
        out.append("    p.rx = %s; p.ry = %s; p.gx = %s; p.gy = %s; p.bx = %s; p.by = %s;"
                   % tuple(f(v) for v in d["primaries"]))
        out.append("    p.wx = %s; p.wy = %s;" % tuple(f(v) for v in d["whitepoint"]))
        for field, key in (("xyz_to_base", "xyz_to_base_t"), ("pipe_to_base", "pipe_to_base_t"),
                           ("base_to_pipe", "base_to_pipe_t")):
            lead = "    p.%s = " % field
            out.append(lead + mat_make(d[key], len(lead)) + ";")
        out.append("  }")
    out += ["  return p;", "}", ""]
    return out


def dwg_block():
    m = mul3(inv3(npm(REC2020, D65)), npm(DWG, D65))
    return ["// DaVinci Wide Gamut -> Rec2020, ambos con blanco D65 (0.3127, 0.3290)",
            "__DEVICE__ agx_mat agx_dwg_to_rec2020()",
            "{",
            "  return " + mat_make(transposed(m), 9) + ";",
            "}",
            ""]


def presets_block():
    out = ["// Presets de darktable (init_presets en agx.c). 1 scene-referred default, 2 blender-like base,",
           "// 3 blender-like punchy, 4 sigmoid-like default, 5 sigmoid-like smooth, 6 smooth,",
           "// 7 unmodified base primaries",
           "__DEVICE__ agx_params agx_preset(int preset, agx_params p)",
           "{"]
    for idx, name in enumerate(PRESETS, start=1):
        out.append(("  if(preset == %d)" if idx == 1 else "  else if(preset == %d)") % idx)
        out.append("  {")
        for line in dtref("preset", name).splitlines():
            field, value = line.split()
            if field == "dynamic_range_scaling":
                continue
            if field == "base_primaries":
                out.append("    p.base_primaries = %d;" % DT_BASE_TO_DCTL[int(float(value))])
            elif field in INT_FIELDS:
                out.append("    p.%s = %d;" % (field, int(float(value))))
            else:
                out.append("    p.%s = %s;" % (field, f(float(value))))
        out.append("  }")
    out += ["  return p;", "}", ""]
    return out


def main():
    text = DCTL.read_text()
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    block = "\n".join(profiles_block() + dwg_block() + presets_block())
    new = text[:start] + block + text[end:]
    if "--check" in sys.argv:
        if new != text:
            sys.exit("el bloque generado del DCTL no esta al dia: corre test/gen_consts.py")
        return
    DCTL.write_text(new)


if __name__ == "__main__":
    main()
