#!/usr/bin/env python3
"""Revisa que el DCTL compile en los lenguajes a los que lo traduce Resolve.

Resolve compila el DCTL como CUDA, OpenCL o Metal segun la GPU. Sin Resolve ni GPU,
esto es lo mas cercano:
- lint: solo ASCII, todo literal float con sufijo f, solo funciones de la lista de DCTL
  y ningun identificador reservado en OpenCL o Metal;
- OpenCL C 1.2 con clang (sin doubles, tipos vectoriales nativos);
- C++14 con g++ (Metal Shading Language es C++14).
Uso: compat.py [archivo.dctl]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from dctl2c import split_args

HERE = Path(__file__).resolve().parent

# funciones flotantes de la documentacion de DCTL (Resolve 17 en adelante; _floor y _ceil
# estan deprecadas desde 17.0)
DCTL_FUNCS = {"_fabs", "_powf", "_logf", "_log2f", "_log10f", "_expf", "_exp2f", "_exp10f", "_copysignf",
              "_fmaxf", "_fminf", "_clampf", "_saturatef", "_sqrtf", "_ceilf", "_floorf", "_truncf", "_round",
              "_fmod", "_hypotf", "_cosf", "_sinf", "_cospif", "_sinpif", "_tanf", "_acosf", "_asinf",
              "_atan2f", "_acoshf", "_asinhf", "_atanhf", "_coshf", "_sinhf", "_tanhf", "_fdimf", "_fmaf",
              "_rsqrtf", "_fdivide", "_frecip", "_mix", "_frexp", "_ldexp"}
# palabras reservadas o funciones nativas de OpenCL C y Metal que no deben usarse como nombres
RESERVED = {"half", "device", "constant", "thread", "threadgroup", "kernel", "vertex", "fragment",
            "sampler", "texture", "global", "local", "private", "read_only", "write_only", "image",
            "min", "max", "clamp", "mix", "step", "sign", "dot", "length", "normalize", "fract", "select",
            "distance", "degrees", "radians", "smoothstep", "saturate", "rotate", "cross", "uint",
            "uchar", "ushort", "bool", "auto", "new", "delete", "this", "class", "template", "namespace"}


def ui_params(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"^DEFINE_UI_PARAMS\((.*)\)\s*$", line)
        if m:
            args = split_args(m.group(1))
            enums = args[4].strip("{} ") if args[2] == "DCTLUI_COMBO_BOX" else None
            out.append((line, args[0], args[2], args[3], enums))
    return out


def lint(text):
    errors = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(ord(c) > 127 for c in line):
            errors.append(f"linea {i}: caracter no ASCII")
        if line.startswith("DEFINE_UI_PARAMS"):
            continue
        code = re.sub(r"//.*", "", line)
        for lit in re.finditer(r"(?<![\w.])(\d+\.\d*(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+|\.\d+)(?![\w.])", code):
            errors.append(f"linea {i}: literal sin sufijo f: {lit.group(1)}")
        for fn in re.finditer(r"\b(_[a-z][a-z0-9]*)\s*\(", code):
            if fn.group(1) not in DCTL_FUNCS:
                errors.append(f"linea {i}: funcion fuera de la lista de DCTL: {fn.group(1)}")
        for ident in re.finditer(r"\b(?:float[23]?|int|agx_\w+)\s+(\w+)\s*[=;,)]", code):
            if ident.group(1) in RESERVED:
                errors.append(f"linea {i}: nombre reservado en OpenCL/Metal: {ident.group(1)}")
    # Resolve halla la funcion principal buscando el texto "transform": si aparece antes en otro
    # lado, cuenta los argumentos de lo que siga y falla con "wrong number of arguments".
    hits = [i for i, line in enumerate(text.splitlines(), 1) if "transform" in line.lower()]
    if len(hits) != 1:
        errors.append(f"lineas {hits}: el texto 'transform' solo puede aparecer en la firma de transform()")
    return errors


def translate(text, ui_line):
    lines = text.splitlines()
    params = {p[0]: p for p in ui_params(text)}
    out = []
    for line in lines:
        if line in params:
            out.append(ui_line(*params[line][1:]))
        else:
            out.append(line)
    return "\n".join(out) + "\n"


OPENCL_PRELUDE = """\
#define __DEVICE__ inline
#define make_float2(x, y) ((float2)((x), (y)))
#define make_float3(x, y, z) ((float3)((x), (y), (z)))
#define _fabs fabs
#define _powf pow
#define _log2f log2
#define _exp2f exp2
#define _fmaxf fmax
#define _fminf fmin
#define _sqrtf sqrt
#define _floorf floor
#define _cosf cos
#define _sinf sin
#define _atan2f atan2
"""

OPENCL_KERNEL = """
kernel void agx_kernel(global const float *in, global float *out, int w, int h)
{
  const int x = get_global_id(0), y = get_global_id(1);
  const int i = 3 * (y * w + x);
  const float3 o = transform(w, h, x, y, in[i], in[i + 1], in[i + 2]);
  out[i] = o.x; out[i + 1] = o.y; out[i + 2] = o.z;
}
"""

CPP_PRELUDE = """\
#include <cmath>
struct float2 { float x, y; };
struct float3 { float x, y, z; };
static inline float2 make_float2(float x, float y) { return float2{x, y}; }
static inline float3 make_float3(float x, float y, float z) { return float3{x, y, z}; }
#define __DEVICE__ static inline
#define _fabs std::fabs
#define _powf std::pow
#define _log2f std::log2
#define _exp2f std::exp2
#define _fmaxf std::fmax
#define _fminf std::fmin
#define _sqrtf std::sqrt
#define _floorf std::floor
#define _cosf std::cos
#define _sinf std::sin
#define _atan2f std::atan2
using std::isnan;
"""


def opencl_ui(name, kind, default, enums):
    if kind == "DCTLUI_COMBO_BOX":
        return f"enum {{ {enums} }}; constant int {name} = {default};"
    if kind == "DCTLUI_CHECK_BOX":
        return f"constant int {name} = {default};"
    return f"constant float {name} = {default}f;"


def cpp_ui(name, kind, default, enums):
    if kind == "DCTLUI_COMBO_BOX":
        return f"enum {{ {enums} }}; static int {name} = {default};"
    if kind == "DCTLUI_CHECK_BOX":
        return f"static int {name} = {default};"
    return f"static float {name} = {default}f;"


def compile_check(label, cmd, source):
    with tempfile.NamedTemporaryFile("w", suffix=Path(cmd[-1]).suffix or ".txt", delete=False,
                                     dir=HERE / "build") as fh:
        fh.write(source)
    r = subprocess.run(cmd[:-1] + [fh.name], capture_output=True, text=True)
    Path(fh.name).unlink()
    ok = r.returncode == 0
    print("%-4s %s" % ("ok" if ok else "MAL", label))
    if not ok:
        print(r.stderr[-4000:])
    return ok


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "AgX_darktable.dctl"
    text = path.read_text()
    (HERE / "build").mkdir(exist_ok=True)

    errors = lint(text)
    print("%-4s lint (ASCII, sufijos f, funciones de DCTL, nombres reservados)" % ("ok" if not errors else "MAL"))
    for e in errors:
        print("     " + e)

    ok = not errors
    ok &= compile_check("OpenCL C 1.2 (clang)",
                        ["clang", "-x", "cl", "-cl-std=CL1.2", "-Xclang", "-finclude-default-header",
                         "-fsyntax-only", "-Werror", "-Wall", "-Wno-unused-function", "x.cl"],
                        OPENCL_PRELUDE + translate(text, opencl_ui) + OPENCL_KERNEL)
    ok &= compile_check("C++14 (g++, como Metal)",
                        ["g++", "-x", "c++", "-std=c++14", "-fsyntax-only", "-Werror", "-Wall",
                         "-Wno-unused-function", "x.cpp"],
                        CPP_PRELUDE + translate(text, cpp_ui))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
