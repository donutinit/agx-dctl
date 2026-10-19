#!/usr/bin/env python3
"""Convierte el .dctl en C para correrlo en CPU con dctl_shim.h.

Cada DEFINE_UI_PARAMS se vuelve una variable global con su valor por defecto (los combos
tambien generan su enum) y se agrega una tabla para cambiarlas por nombre. El resto del
archivo pasa sin cambios. Uso: dctl2c.py <archivo.dctl> <salida.c>
"""
import re
import sys
from pathlib import Path


def split_args(text):
    args, depth, cur = [], 0, ""
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    args.append(cur.strip())
    return args


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    body, table = [], []
    for line in src.read_text().splitlines():
        m = re.match(r"^DEFINE_UI_PARAMS\((.*)\)\s*$", line)
        if not m:
            body.append(line)
            continue
        args = split_args(m.group(1))
        name, kind, default = args[0], args[2], args[3]
        if kind == "DCTLUI_SLIDER_FLOAT":
            if not re.search(r"[.eE]", default):
                default += ".0"
            body.append(f"static float {name} = {default}f;")
            table.append(f'  {{ "{name}", \'f\', &{name} }},')
        elif kind in ("DCTLUI_CHECK_BOX", "DCTLUI_SLIDER_INT"):
            body.append(f"static int {name} = {default};")
            table.append(f'  {{ "{name}", \'i\', &{name} }},')
        elif kind == "DCTLUI_COMBO_BOX":
            enums = args[4].strip("{} ")
            body.append(f"enum {{ {enums} }}; static int {name} = {default};")
            table.append(f'  {{ "{name}", \'i\', &{name} }},')
        else:
            sys.exit(f"tipo de control no soportado: {kind}")

    text = ['#include "dctl_shim.h"', "#line 1 \"" + src.name + "\""] + body
    text += ["", "typedef struct { const char *name; char kind; void *ptr; } ui_param_t;",
             "static ui_param_t ui_params[] = {"] + table + ["  { 0, 0, 0 }", "};", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(text) + "\n")


if __name__ == "__main__":
    main()
