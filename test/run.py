#!/usr/bin/env python3
"""Compara el DCTL contra el AgX de darktable, pixel por pixel.

1. Arma una carta en Rec2020 lineal: rampa de grises de -16 a +16 EV, barrido de tonos
   con saturaciones dentro y fuera de gamut, colores al azar y casos raros (negativos,
   NaN, infinito, valores enormes).
2. La procesa con la referencia (build/dtref, codigo de darktable) y con el DCTL
   compilado como C (build/dctl_run), con los presets de darktable y con cientos de
   combinaciones de parametros al azar.
3. Revisa tambien la entrada DaVinci Intermediate / DWG, las salidas codificadas, que
   el combo de presets de igual que los sliders y que los valores por defecto del DCTL
   sean el "scene-referred default" de darktable.

Uso: run.py [--seed N] [--random N]
"""
import argparse
import array
import math
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
PRESETS = ["scene-referred-default", "blender-like-base", "blender-like-punchy", "sigmoid-like-default",
           "sigmoid-like-smooth", "smooth", "unmodified-base-primaries"]
DT_BASE_TO_DCTL = {0: 3, 1: 0, 2: 0, 3: 1, 4: 2, 5: 3}

# tolerancias: diferencia absoluta en salida lineal de display (0 a 1)
TOL_CORE = 2e-5
TOL_DI = 2e-4
TOL_GPU = 1e-3


# ---------- carta ----------

def hue_rgb(h):
    """color saturado con maximo 1 y minimo 0 (h en grados)"""
    h = (h % 360.0) / 60.0
    i, f = int(h), h - int(h)
    return [(1, f, 0), (1 - f, 1, 0), (0, 1, f), (0, 1 - f, 1), (f, 0, 1), (1, 0, 1 - f)][i % 6]


def chart(seed):
    rnd = random.Random(seed)
    px = []
    ev = -16.0
    while ev <= 16.0:
        v = 0.18 * 2 ** ev
        px.append((v, v, v))
        ev += 0.125
    for h in range(0, 360, 6):
        for c in (0.15, 0.4, 0.7, 0.9, 1.0, 1.15, 1.5):
            for ev in range(-8, 12, 2):
                v = 0.18 * 2 ** ev
                r, g, b = hue_rgb(h)
                px.append(tuple(v * (1 - c + c * k) for k in (r, g, b)))
    for _ in range(3000):
        lum = 0.18 * 2 ** rnd.uniform(-20, 13)
        px.append(tuple(lum * rnd.uniform(-0.3, 1.3) for _ in range(3)))
    px += [(0, 0, 0), (-1, -1, -1), (1e-12, 1e-12, 1e-12), (1e7, 0, 0), (0, 1e7, 1e7), (-5, 2, 0.5),
           (float("nan"), 0.2, 0.2), (float("inf"), 0.1, 0.1), (float("-inf"), 0.3, 0.3), (1e6, 1e6, 1e6)]
    return px


def write_f32(path, px):
    array.array("f", [c for p in px for c in p]).tofile(open(path, "wb"))


def read_f32(path):
    a = array.array("f")
    a.frombytes(Path(path).read_bytes())
    return [tuple(a[i:i + 3]) for i in range(0, len(a), 3)]


# ---------- parametros ----------

def dtref(*args):
    return subprocess.run([str(BUILD / "dtref"), *args], check=True, capture_output=True, text=True).stdout


def preset_params(name):
    return {k: float(v) for k, v in (line.split() for line in dtref("preset", name).splitlines())}


def random_params(rnd):
    def pick(default, lo, hi, p_default=0.25):
        return default if rnd.random() < p_default else rnd.uniform(lo, hi)

    black = pick(-10.0, -20.0, -0.1)
    white = pick(6.5, 0.1, 20.0)
    p = {
        "look_lift": pick(0.0, -0.9, 1.0),
        "look_slope": pick(1.0, 0.0, 3.0),
        "look_brightness": pick(1.0, 0.0, 4.0),
        "look_saturation": pick(1.0, 0.0, 3.0),
        "look_original_hue_mix_ratio": pick(0.6, 0.0, 1.0),
        "range_black_relative_ev": black,
        "range_white_relative_ev": white,
        "dynamic_range_scaling": 0.1,
        "curve_pivot_x": pick(-black / (white - black), 0.0, 1.0),
        "curve_pivot_y_linear_output": pick(0.18, 0.0, 1.0),
        "curve_contrast_around_pivot": pick(3.0, 0.1, 10.0),
        "curve_linear_ratio_below_pivot": pick(0.0, 0.0, 1.0, 0.5),
        "curve_linear_ratio_above_pivot": pick(0.0, 0.0, 1.0, 0.5),
        "curve_toe_power": pick(1.5, 0.0, 10.0),
        "curve_shoulder_power": pick(3.3, 0.0, 10.0),
        "curve_gamma": pick(2.2, 0.01, 10.0),
        "auto_gamma": float(rnd.random() < 0.25),
        "curve_target_display_black_ratio": pick(0.0, 0.0, 0.15, 0.5),
        "curve_target_display_white_ratio": pick(1.0, 0.2, 1.0, 0.5),
        "base_primaries": float(rnd.choice([0, 1, 2, 2, 2, 3, 4, 5])),
        "disable_primaries_adjustments": float(rnd.random() < 0.1),
        "completely_reverse_primaries": float(rnd.random() < 0.15),
        "master_outset_ratio": pick(1.0, 0.0, 2.0),
        "master_unrotation_ratio": pick(1.0, 0.0, 2.0),
    }
    for c in ("red", "green", "blue"):
        p[c + "_inset"] = rnd.uniform(0.0, 0.99)
        p[c + "_rotation"] = rnd.uniform(-0.5236, 0.5236)
        p[c + "_outset"] = rnd.uniform(0.0, 0.99)
        p[c + "_unrotation"] = rnd.uniform(-0.5236, 0.5236)
    return p


def dctl_controls(p):
    """parametros de darktable a controles del DCTL, en las unidades de la interfaz"""
    deg = 180.0 / math.pi
    black, white = p["range_black_relative_ev"], p["range_white_relative_ev"]
    ui = {
        "p_preset": 0, "p_input": 2, "p_exposure": 0.0, "p_output": 4, "p_show_curve": 0,
        "p_white_ev": white,
        "p_black_ev": black,
        "p_pivot_ev": black + p["curve_pivot_x"] * (white - black),
        "p_pivot_out": p["curve_pivot_y_linear_output"] * 100,
        "p_contrast": p["curve_contrast_around_pivot"],
        "p_shoulder_power": p["curve_shoulder_power"],
        "p_toe_power": p["curve_toe_power"],
        "p_look_slope": p["look_slope"],
        "p_look_lift": p["look_lift"],
        "p_look_brightness": p["look_brightness"],
        "p_look_saturation": p["look_saturation"] * 100,
        "p_look_hue": p["look_original_hue_mix_ratio"] * 100,
        "p_shoulder_start": p["curve_linear_ratio_above_pivot"] * 100,
        "p_target_white": p["curve_target_display_white_ratio"] * 100,
        "p_toe_start": p["curve_linear_ratio_below_pivot"] * 100,
        "p_target_black": p["curve_target_display_black_ratio"] * 100,
        "p_auto_gamma": int(p["auto_gamma"]),
        "p_curve_gamma": p["curve_gamma"],
        "p_base": DT_BASE_TO_DCTL[int(p["base_primaries"])],
        "p_disable_primaries": int(p["disable_primaries_adjustments"]),
        "p_reverse_all": int(p["completely_reverse_primaries"]),
        "p_master_outset": p["master_outset_ratio"] * 100,
        "p_master_unrotation": p["master_unrotation_ratio"] * 100,
    }
    for c in ("red", "green", "blue"):
        ui[f"p_{c}_inset"] = p[c + "_inset"] * 100
        ui[f"p_{c}_rotation"] = p[c + "_rotation"] * deg
        ui[f"p_{c}_outset"] = p[c + "_outset"] * 100
        ui[f"p_{c}_unrotation"] = p[c + "_unrotation"] * deg
    return ui


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


INT_CONTROLS = {"p_preset", "p_input", "p_output", "p_show_curve", "p_auto_gamma", "p_base",
                "p_disable_primaries", "p_reverse_all"}


def as_float32(ui):
    """los sliders del DCTL son float: redondea como lo haria Resolve"""
    return {k: (v if k in INT_CONTROLS else f32(v)) for k, v in ui.items()}


def params_from_controls(ui):
    """lo mismo que calcula transform() con los sliders, operacion por operacion en float32.

    Con ajustes extremos el AgX de darktable cambia aunque un parametro se mueva un solo
    bit, asi que la referencia tiene que recibir exactamente los mismos floats."""
    g = lambda k: f32(ui[k])
    pct = lambda k: f32(g(k) / 100.0)
    deg = f32(f32(math.pi) / 180.0)
    rot = lambda k: f32(g(k) * deg)
    black, white = g("p_black_ev"), g("p_white_ev")
    pivot = f32(f32(g("p_pivot_ev") - black) / f32(white - black))
    p = {
        "look_lift": g("p_look_lift"),
        "look_slope": g("p_look_slope"),
        "look_brightness": g("p_look_brightness"),
        "look_saturation": pct("p_look_saturation"),
        "look_original_hue_mix_ratio": pct("p_look_hue"),
        "range_black_relative_ev": black,
        "range_white_relative_ev": white,
        "curve_pivot_x": min(max(pivot, 0.0), 1.0),
        "curve_pivot_y_linear_output": pct("p_pivot_out"),
        "curve_contrast_around_pivot": g("p_contrast"),
        "curve_linear_ratio_below_pivot": pct("p_toe_start"),
        "curve_linear_ratio_above_pivot": pct("p_shoulder_start"),
        "curve_toe_power": g("p_toe_power"),
        "curve_shoulder_power": g("p_shoulder_power"),
        "curve_gamma": g("p_curve_gamma"),
        "auto_gamma": ui["p_auto_gamma"],
        "curve_target_display_black_ratio": pct("p_target_black"),
        "curve_target_display_white_ratio": pct("p_target_white"),
        "base_primaries": {0: 2, 1: 3, 2: 4, 3: 5}[ui["p_base"]],
        "disable_primaries_adjustments": ui["p_disable_primaries"],
        "completely_reverse_primaries": ui["p_reverse_all"],
        "master_outset_ratio": pct("p_master_outset"),
        "master_unrotation_ratio": pct("p_master_unrotation"),
    }
    for c in ("red", "green", "blue"):
        p[c + "_inset"] = pct(f"p_{c}_inset")
        p[c + "_rotation"] = rot(f"p_{c}_rotation")
        p[c + "_outset"] = pct(f"p_{c}_outset")
        p[c + "_unrotation"] = rot(f"p_{c}_unrotation")
    return p


def write_kv(path, d):
    Path(path).write_text("".join("%s %.17g\n" % (k, v) for k, v in d.items()))


# ---------- correr y comparar ----------

class Runner:
    def __init__(self, tmp, px):
        self.tmp = Path(tmp)
        self.chart = self.tmp / "chart.f32"
        write_f32(self.chart, px)
        self.n = 0

    def _path(self, ext):
        self.n += 1
        return self.tmp / f"{self.n}.{ext}"

    def reference(self, params, chart=None):
        pf, out = self._path("txt"), self._path("f32")
        write_kv(pf, params)
        subprocess.run([str(BUILD / "dtref"), "process", str(pf), str(chart or self.chart), str(out)], check=True)
        return read_f32(out)

    def dctl(self, controls, chart=None, binary="dctl_run"):
        pf, out = self._path("txt"), self._path("f32")
        write_kv(pf, controls)
        subprocess.run([str(BUILD / binary), str(pf), str(chart or self.chart), str(out)], check=True)
        return read_f32(out)


def max_diff(a, b):
    worst, where = 0.0, None
    for i, (pa, pb) in enumerate(zip(a, b)):
        for ca, cb in zip(pa, pb):
            if math.isnan(ca) and math.isnan(cb):
                continue
            if math.isnan(ca) or math.isnan(cb):
                return float("inf"), i
            d = abs(ca - cb) / max(1.0, abs(ca))
            if d > worst:
                worst, where = d, i
    return worst, where


def srgb_code(v):
    v = min(max(v, 0.0), 1.0)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def max_code_diff(a, b, bits=10):
    """diferencia maxima en valores de codigo, codificando en sRGB"""
    scale = 2 ** bits - 1
    worst = 0
    for pa, pb in zip(a, b):
        for ca, cb in zip(pa, pb):
            if math.isnan(ca) or math.isnan(cb):
                continue
            worst = max(worst, abs(round(srgb_code(ca) * scale) - round(srgb_code(cb) * scale)))
    return worst


# ---------- entrada DaVinci Intermediate / DWG ----------

DWG = [(0.8000, 0.3130), (0.1682, 0.9877), (0.0790, -0.1155)]
REC2020 = [(0.708, 0.292), (0.170, 0.797), (0.131, 0.046)]
D65 = (0.3127, 0.3290)
# DaVinci Wide Gamut a XYZ, como lo publica Blackmagic en su documento de DWG/Intermediate
DWG_TO_XYZ_PUBLISHED = [[0.70062239, 0.14877482, 0.10105872],
                        [0.27411851, 0.87363190, -0.14775041],
                        [-0.09896291, -0.13789533, 1.32591599]]


def inv3(m):
    a, b, c = m[0]
    d, e, g = m[1]
    h, i, j = m[2]
    det = a * (e * j - g * i) - b * (d * j - g * h) + c * (d * i - e * h)
    return [[(e * j - g * i) / det, (c * i - b * j) / det, (b * g - c * e) / det],
            [(g * h - d * j) / det, (a * j - c * h) / det, (c * d - a * g) / det],
            [(d * i - e * h) / det, (b * h - a * i) / det, (a * e - b * d) / det]]


def npm(primaries, white):
    p = [[x / y for x, y in primaries], [1.0, 1.0, 1.0], [(1 - x - y) / y for x, y in primaries]]
    w = [white[0] / white[1], 1.0, (1 - white[0] - white[1]) / white[1]]
    pi = inv3(p)
    s = [sum(pi[r][k] * w[k] for k in range(3)) for r in range(3)]
    return [[p[r][c] * s[c] for c in range(3)] for r in range(3)]


def mat_vec(m, v):
    return tuple(sum(m[r][k] * v[k] for k in range(3)) for r in range(3))


def lin_to_di(x):
    if x <= 0.00262409:
        return x * 10.44426855
    return (math.log2(x + 0.0075) + 7.0) * 0.07329248


# ---------- pruebas ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--random", type=int, default=300)
    args = ap.parse_args()

    subprocess.run(["make", "-s", "-C", str(HERE)], check=True)
    subprocess.run([sys.executable, str(HERE / "gen_consts.py"), "--check"], check=True)
    print("compatibilidad con GPU:", flush=True)
    subprocess.run([sys.executable, str(HERE / "compat.py")], check=True)
    print()

    px = chart(args.seed)
    rnd = random.Random(args.seed)
    failures = []

    def check(label, value, limit, extra=""):
        ok = value <= limit
        print("%-4s %-46s %.3g%s" % ("ok" if ok else "MAL", label, value, extra))
        if not ok:
            failures.append(label)

    with tempfile.TemporaryDirectory(dir=BUILD) as tmp:
        run = Runner(tmp, px)
        print("carta: %d pixeles\n" % len(px))

        print("presets de darktable vs DCTL (sliders):")
        for name in PRESETS:
            p = preset_params(name)
            ref = run.reference(p)
            got = run.dctl(dctl_controls(p))
            d, where = max_diff(ref, got)
            check(name, d, TOL_CORE, "   (codigo 10 bits: %d)" % max_code_diff(ref, got))

        print("\ncombo de presets del DCTL = sliders con esos valores:")
        for k, name in enumerate(PRESETS, start=1):
            p = preset_params(name)
            via_sliders = run.dctl(dctl_controls(p))
            ui = dctl_controls(preset_params("unmodified-base-primaries"))
            ui["p_preset"] = k
            via_combo = run.dctl(ui)
            check(name, max_diff(via_sliders, via_combo)[0], 1e-6)

        print("\nvalores por defecto del DCTL = scene-referred default:")
        defaults = run.dctl({"p_input": 2, "p_output": 4})
        ref = run.reference(preset_params("scene-referred-default"))
        check("defaults", max_diff(ref, defaults)[0], TOL_CORE)

        print("\n%d combinaciones de parametros al azar:" % args.random)
        worst, worst_code, worst_case = 0.0, 0, None
        for i in range(args.random):
            ui = as_float32(dctl_controls(random_params(rnd)))
            p = params_from_controls(ui)
            ref = run.reference(p)
            got = run.dctl(ui)
            d, where = max_diff(ref, got)
            if d > worst:
                worst, worst_case = d, (i, where, p)
            worst_code = max(worst_code, max_code_diff(ref, got))
        check("peor diferencia", worst, TOL_CORE, "   (codigo 10 bits: %d)" % worst_code)
        if worst > TOL_CORE:
            i, where, p = worst_case
            print("     caso %d, pixel %d %s" % (i, where, px[where]))
            print("     " + " ".join("%s=%.6g" % kv for kv in p.items()))

        # solo valores que DaVinci Intermediate puede representar (1.0 en DI es ~100 lineal): con
        # cian a 1e7 o rojo a -inf el tono que recupera "preserve hue" depende de cual de dos
        # canales casi iguales es mayor, y cualquier error de redondeo lo voltea
        real = [i for i, p_ in enumerate(px) if all(abs(c) <= 1000 for c in p_)]
        print("\nsimulacion de GPU (pow, log2, atan2... con error de hasta 4 ulp), %d pixeles:" % len(real))
        for name in PRESETS:
            ui = as_float32(dctl_controls(preset_params(name)))
            ref_all = run.reference(params_from_controls(ui))
            got_all = run.dctl(ui, binary="dctl_run_gpusim")
            ref = [ref_all[i] for i in real]
            got = [got_all[i] for i in real]
            check(name, max_diff(ref, got)[0], TOL_GPU, "   (codigo 10 bits: %d)" % max_code_diff(ref, got))

        print("\nentrada DaVinci Intermediate / DWG:")
        npm_dwg = npm(DWG, D65)
        d = max(abs(npm_dwg[r][c] - DWG_TO_XYZ_PUBLISHED[r][c]) for r in range(3) for c in range(3))
        check("DWG a XYZ = matriz publicada por Blackmagic", d, 1e-7)
        rec2020_to_dwg = [[sum(inv3(npm_dwg)[r][k] * npm(REC2020, D65)[k][c] for k in range(3)) for c in range(3)]
                          for r in range(3)]
        di_px = []
        for p_ in px:
            if any(math.isnan(c) or math.isinf(c) or abs(c) > 50 for c in p_):
                di_px.append((0.0, 0.0, 0.0))
                continue
            dwg = mat_vec(rec2020_to_dwg, p_)
            # DI no representa valores menores que su corte lineal negativo; se quedan lineales
            di_px.append(tuple(lin_to_di(c) for c in dwg))
        keep = [i for i, p_ in enumerate(px) if not any(math.isnan(c) or math.isinf(c) or abs(c) > 50 for c in p_)]
        di_chart = Path(tmp) / "chart_di.f32"
        write_f32(di_chart, di_px)
        for name in ("scene-referred-default", "sigmoid-like-smooth"):
            p = preset_params(name)
            ref = run.reference(p)
            ui = dctl_controls(p)
            ui["p_input"] = 0
            got = run.dctl(ui, di_chart)
            d = max_diff([ref[i] for i in keep], [got[i] for i in keep])[0]
            check("DI DWG, " + name, d, TOL_DI,
                  "   (codigo 10 bits: %d)" % max_code_diff([ref[i] for i in keep], [got[i] for i in keep]))

        print("\nsalidas codificadas (contra la salida lineal del DCTL):")
        p = preset_params("scene-referred-default")
        base_ui = dctl_controls(p)
        linear = run.dctl(base_ui)
        consts = {}
        for line in dtref("consts").splitlines():
            name, key, *vals = line.split()
            consts[(name, key)] = [float(v) for v in vals]

        def transposed_apply(m, v):
            return tuple(m[0 * 3 + r] * v[0] + m[1 * 3 + r] * v[1] + m[2 * 3 + r] * v[2] for r in range(3))

        clip = lambda x: min(max(x, 0.0), 1.0)
        outputs = {
            0: lambda v: tuple(clip(c) ** (1 / 2.4) for c in transposed_apply(consts[("srgb", "pipe_to_base_t")], v)),
            1: lambda v: tuple(srgb_code(c) for c in transposed_apply(consts[("srgb", "pipe_to_base_t")], v)),
            2: lambda v: tuple(srgb_code(c) for c in transposed_apply(consts[("p3", "pipe_to_base_t")], v)),
            3: lambda v: tuple(clip(c) ** (1 / 2.4) for c in v),
        }
        names = {0: "Rec.709 Gamma 2.4", 1: "sRGB", 2: "Display P3", 3: "Rec.2020 Gamma 2.4"}
        for out_mode, fn in outputs.items():
            ui = dict(base_ui, p_output=out_mode)
            got = run.dctl(ui)
            expected = [fn(v) if not any(math.isnan(c) for c in v) else v for v in linear]
            check(names[out_mode], max_diff(expected, got)[0], 1e-5)

    print()
    if failures:
        print("FALLARON: " + ", ".join(failures))
        sys.exit(1)
    print("todo coincide")


if __name__ == "__main__":
    main()
