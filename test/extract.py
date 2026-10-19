#!/usr/bin/env python3
"""Copia tal cual las funciones y tipos de darktable que usa la referencia.

No se reescribe nada a mano: el C de la referencia es el de darktable,
recortado por nombre de funcion. Uso: extract.py <upstream/darktable> <salida.inc>
"""
import re
import sys
from pathlib import Path

# (archivo, [funciones]) en orden de dependencia
FUNCS = [
    ("dttypes.h", ["transpose_3xSSE", "dt_colormatrix_mul", "dt_colormatrix_transpose",
                   "max3f", "min3f"]),
    ("matrices.c", ["mat3SSEinv"]),
    ("colorspaces_inline_conversions.h", ["dt_D50_XYZ_to_xyY", "dt_apply_transposed_color_matrix", "_dt_RGB_2_Hue",
                                          "_dt_Hue_2_RGB", "dt_RGB_2_HSV", "dt_HSV_2_RGB"]),
    ("custom_primaries.c", ["_determinant", "_intersect_line_segments", "_find_distance_to_edge",
                            "dt_rotate_and_scale_primary"]),
    ("colorspaces.c", ["_colorspaces_get_matrix_from_profile",
                       "dt_colorspaces_get_matrix_from_input_profile",
                       "dt_colorspaces_get_matrix_from_output_profile",
                       "_create_lcms_profile", "_colorspaces_create_srgb_profile",
                       "dt_colorspaces_create_srgb_profile", "dt_colorspaces_create_adobergb_profile",
                       "_colorspaces_create_linear_rec2020_rgb_profile",
                       "_colorspaces_create_display_p3_rgb_profile",
                       "cmsCIEXYZ_to_xy", "dt_colorspaces_get_primaries_and_whitepoint_from_profile", "_sanitizeY",
                       "dt_make_transposed_matrices_from_primaries_and_whitepoint"]),
]

AGX_TYPES = ["dt_iop_agx_base_primaries_t", "dt_iop_agx_params_t", "tone_mapping_params_t",
             "primaries_params_t", "dt_iop_agx_data_t"]

AGX_FUNCS = [
    "_get_base_profile_type_from_enum", "_set_blenderlike_primaries", "_set_unmodified_primaries",
    "_set_smooth_primaries", "_agx_get_base_profile", "_luminance_from_matrix", "_line", "_scale",
    "_sigmoid", "_scaled_sigmoid", "_fallback_toe", "_fallback_shoulder", "_apply_curve",
    "_lerp_hue", "_apply_slope_lift", "_agx_look", "_apply_log_encoding",
    "_calculate_slope_matching_power", "_calculate_fallback_curve_coefficient",
    "_compress_into_gamut", "_calculate_pivot_y_at_gamma", "_adjust_pivot",
    "_set_log_mapping_params", "_calculate_slope_gamma_compensation",
    "_calculate_tone_mapping_params", "_get_primaries_params", "_agx_tone_mapping",
    "_create_matrices", "process", "_set_default_curve_and_look_params", "_set_neutral_params",
    "_set_smooth_params", "_set_blenderlike_params", "_set_scene_referred_default_params",
    "_make_punchy",
]

TYPE_START = re.compile(r"^(?:static\s+|inline\s+|const\s+)*[A-Za-z_][\w\s\*]*$")


def function(lines, name, path):
    pat = re.compile(r"(?:^|[\s\*])" + re.escape(name) + r"\s*(?:\(|$)")
    for i, line in enumerate(lines):
        indent = len(line) - len(line.lstrip(" "))
        if indent > 1 or not pat.search(line):
            continue
        # el nombre puede ir solo en su linea y el "(" en la siguiente
        after = line.split(name, 1)[1].strip() or (lines[i + 1].strip() if i + 1 < len(lines) else "")
        if not after.startswith("("):
            continue
        stripped = line.strip()
        if stripped.startswith(("return", "//", "*", "/*", "#")) or "=" in stripped.split("(")[0]:
            continue
        # tiene que ser una definicion: aparece '{' antes que ';'
        j, text = i, ""
        while j < len(lines):
            text += lines[j]
            if "{" in lines[j] or ";" in lines[j]:
                break
            j += 1
        if "{" not in lines[j] or (";" in lines[j] and lines[j].index(";") < lines[j].index("{")):
            continue
        # tipo de retorno en la linea anterior (p. ej. "static inline foo_t\n_nombre(")
        start = i
        while start > 0:
            prev = lines[start - 1]
            if prev and not prev[0].isspace() and TYPE_START.match(prev) and not prev.startswith(("#", "/", "*")):
                start -= 1
            else:
                break
        end = j
        while lines[end].rstrip() != "}":
            end += 1
        return "".join(lines[start:end + 1])
    sys.exit(f"no encontre la funcion {name} en {path}")


def typedef(text, name):
    m = re.search(r"^typedef (?:enum|struct) " + re.escape(name) + r"\b.*?^\} " + re.escape(name) + ";",
                  text, re.S | re.M)
    if not m:
        sys.exit(f"no encontre el tipo {name}")
    return m.group(0)


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    parts = ["/* generado por test/extract.py desde darktable; no editar */\n"]

    cs = (src / "colorspaces.c").read_text()
    for prim in ["sRGB_Primaries", "Rec2020_Primaries", "Adobe_Primaries", "P3_Primaries"]:
        m = re.search(r"^static const cmsCIExyYTRIPLE " + prim + r" = \{.*?^\};", cs, re.S | re.M)
        parts.append(m.group(0) + "\n")
    hdr = (src / "colorspaces.h").read_text()
    for wp in ["D50xyY", "D65xyY"]:
        parts.append(re.search(r"^static const cmsCIExyY " + wp + r" = .*$", hdr, re.M).group(0) + "\n")

    for fname, names in FUNCS:
        lines = (src / fname).read_text().splitlines(keepends=True)
        for n in names:
            parts.append(function(lines, n, fname) + "\n")

    agx_text = (src / "agx.c").read_text()
    for t in AGX_TYPES:
        parts.append(typedef(agx_text, t) + "\n")
    parts.extend(m.group(0) + "\n" for m in re.finditer(r"^static const (?:float|int) _\w+ = .*;$", agx_text, re.M))
    agx_lines = agx_text.splitlines(keepends=True)
    for n in AGX_FUNCS:
        parts.append(function(agx_lines, n, "agx.c") + "\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts))


if __name__ == "__main__":
    main()
