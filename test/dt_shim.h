/* Lo minimo de darktable para compilar el codigo extraido de agx.c fuera de darktable.
   Solo tipos, macros y la parte de iop_profile.c que arma los perfiles; la matematica
   de AgX viene tal cual en build/dtref_extract.inc. */
#pragma once
#include <float.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lcms2.h"

typedef int gboolean;
typedef char gchar;
#define TRUE 1
#define FALSE 0

#define DT_ALIGNED_PIXEL __attribute__((aligned(16)))
#define DT_ALIGNED_ARRAY __attribute__((aligned(64)))
typedef DT_ALIGNED_PIXEL float dt_aligned_pixel_t[4];
typedef float DT_ALIGNED_ARRAY dt_colormatrix_t[4][4];
#define DT_PIXEL_SIMD_CHANNELS 4
#define for_each_channel(_var, ...) for(size_t _var = 0; _var < DT_PIXEL_SIMD_CHANNELS; _var++)
#define for_four_channels(_var, ...) for(size_t _var = 0; _var < 4; _var++)
#define for_three_channels(_var, ...) for(size_t _var = 0; _var < 3; _var++)
#define DT_OMP_DECLARE_SIMD(...)
#define DT_OMP_FOR(...)
#define DT_OMP_SIMD(...)

/* common/math.h y darktable.h */
#define M_PI_F 3.14159265358979323846f
#define CLIP(x) (((x) >= 0) ? ((x) <= 1 ? (x) : 1) : 0)
#define CLAMPF(a, mn, mx) ((a) >= (mn) ? ((a) <= (mx) ? (a) : (mx)) : (mn))
#ifdef FP_FAST_FMAF
#define DT_FMA(x, y, z) fmaf(x, y, z)
#else
#define DT_FMA(x, y, z) ((x) * (y) + (z))
#endif
static inline float deg2radf(const float deg) { return deg * M_PI_F / 180.f; }
static inline void copy_pixel(float *const out, const float *const in)
{
  for_each_channel(k) out[k] = in[k];
}
static inline void dt_vector_max(dt_aligned_pixel_t max, const dt_aligned_pixel_t v1,
                                 const dt_aligned_pixel_t v2)
{
  for_each_channel(c) max[c] = fmaxf(v1[c], v2[c]);
}
static inline int dt_is_valid_colormatrix(float matrix) { return isfinite(matrix); }

#define dt_print(...) ((void)0)
#define DT_DEBUG_PIPE 0
#define DT_DEBUG_ALWAYS 0

/* perfiles */
typedef enum dt_colorspaces_color_profile_type_t
{
  DT_COLORSPACE_NONE = -1,
  DT_COLORSPACE_SRGB = 1,
  DT_COLORSPACE_ADOBERGB = 2,
  DT_COLORSPACE_LIN_REC2020 = 4,
  DT_COLORSPACE_DISPLAY_P3 = 22,
} dt_colorspaces_color_profile_type_t;
#define DT_INTENT_PERCEPTUAL INTENT_PERCEPTUAL
#define DT_INTENT_RELATIVE_COLORIMETRIC INTENT_RELATIVE_COLORIMETRIC

typedef struct dt_iop_order_iccprofile_info_t
{
  dt_colorspaces_color_profile_type_t type;
  dt_colormatrix_t matrix_in;
  dt_colormatrix_t matrix_out;
  dt_colormatrix_t matrix_in_transposed;
  dt_colormatrix_t matrix_out_transposed;
  float primaries[3][2];
  float whitepoint[2];
  int nonlinearlut;
} dt_iop_order_iccprofile_info_t;

typedef struct dt_develop_t { int unused; } dt_develop_t;
typedef struct dt_dev_pixelpipe_t { int unused; } dt_dev_pixelpipe_t;
typedef struct dt_iop_module_t { dt_develop_t *dev; } dt_iop_module_t;
typedef struct dt_dev_pixelpipe_iop_t
{
  void *data;
  int colors;
  dt_dev_pixelpipe_t *pipe;
} dt_dev_pixelpipe_iop_t;
typedef struct dt_iop_roi_t { int width, height; } dt_iop_roi_t;

static inline int dt_iop_have_required_input_format(int req, dt_iop_module_t *self, int colors,
                                                    const void *in, void *out,
                                                    const dt_iop_roi_t *ri, const dt_iop_roi_t *ro)
{
  (void)req; (void)self; (void)colors; (void)in; (void)out; (void)ri; (void)ro;
  return 1;
}

static inline const char *dt_colorspaces_get_name(int type, const char *filename)
{
  (void)type; (void)filename;
  return "";
}

/* implementados en dtref.c */
dt_iop_order_iccprofile_info_t *dt_ioppr_add_profile_info_to_list(dt_develop_t *dev,
                                                                  dt_colorspaces_color_profile_type_t type,
                                                                  const char *filename, int intent);
const dt_iop_order_iccprofile_info_t *dt_ioppr_get_pipe_work_profile_info(dt_dev_pixelpipe_t *pipe);
void dt_ioppr_get_export_profile_type(dt_develop_t *dev, dt_colorspaces_color_profile_type_t *type,
                                      const char **filename);
int mat3SSEinv(dt_colormatrix_t dst, const dt_colormatrix_t src);
void dt_rotate_and_scale_primary(const dt_iop_order_iccprofile_info_t *const profile, const float scaling,
                                 const float rotation, const size_t primary_index, float new_xy[2]);
