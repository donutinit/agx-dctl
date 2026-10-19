/* Referencia: el AgX de darktable 5.6.2 corriendo fuera de darktable.
 *
 *   dtref process <params.txt> <entrada.f32> <salida.f32>
 *       procesa pixeles RGB float32 en Rec2020 lineal (el working profile por defecto)
 *   dtref preset <nombre>
 *       imprime los parametros de un preset de darktable
 *   dtref consts
 *       imprime los primarios y matrices de los perfiles base, como los arma darktable
 */
#include "dt_shim.h"
#include "build/dtref_extract.inc"

#define LUTSIZE 0x10000

#define AGX_FIELDS(F)                                                                              \
  F(look_lift, f) F(look_slope, f) F(look_brightness, f) F(look_saturation, f)                     \
  F(look_original_hue_mix_ratio, f) F(range_black_relative_ev, f) F(range_white_relative_ev, f)    \
  F(dynamic_range_scaling, f) F(curve_pivot_x, f) F(curve_pivot_y_linear_output, f)                \
  F(curve_contrast_around_pivot, f) F(curve_linear_ratio_below_pivot, f)                           \
  F(curve_linear_ratio_above_pivot, f) F(curve_toe_power, f) F(curve_shoulder_power, f)            \
  F(curve_gamma, f) F(auto_gamma, i) F(curve_target_display_black_ratio, f)                        \
  F(curve_target_display_white_ratio, f) F(base_primaries, i) F(disable_primaries_adjustments, i)  \
  F(red_inset, f) F(red_rotation, f) F(green_inset, f) F(green_rotation, f) F(blue_inset, f)       \
  F(blue_rotation, f) F(master_outset_ratio, f) F(master_unrotation_ratio, f) F(red_outset, f)     \
  F(red_unrotation, f) F(green_outset, f) F(green_unrotation, f) F(blue_outset, f)                 \
  F(blue_unrotation, f) F(completely_reverse_primaries, i)

static dt_iop_order_iccprofile_info_t *profile_cache[4];

static int _cache_index(const dt_colorspaces_color_profile_type_t type)
{
  switch(type)
  {
    case DT_COLORSPACE_LIN_REC2020: return 0;
    case DT_COLORSPACE_DISPLAY_P3: return 1;
    case DT_COLORSPACE_ADOBERGB: return 2;
    case DT_COLORSPACE_SRGB: return 3;
    default: return -1;
  }
}

static cmsHPROFILE _create_profile(const dt_colorspaces_color_profile_type_t type)
{
  switch(type)
  {
    case DT_COLORSPACE_LIN_REC2020: return _colorspaces_create_linear_rec2020_rgb_profile();
    case DT_COLORSPACE_DISPLAY_P3: return _colorspaces_create_display_p3_rgb_profile();
    case DT_COLORSPACE_ADOBERGB: return dt_colorspaces_create_adobergb_profile();
    case DT_COLORSPACE_SRGB: return dt_colorspaces_create_srgb_profile();
    default: return NULL;
  }
}

/* como _ioppr_generate_profile_info() de iop_profile.c, solo la parte de matrices.
   La busqueda ignora el intent, igual que dt_ioppr_get_profile_info_from_list(). */
dt_iop_order_iccprofile_info_t *dt_ioppr_add_profile_info_to_list(dt_develop_t *dev,
                                                                  dt_colorspaces_color_profile_type_t type,
                                                                  const char *filename, int intent)
{
  (void)dev; (void)filename; (void)intent;
  const int idx = _cache_index(type);
  if(idx < 0) return NULL;
  if(profile_cache[idx]) return profile_cache[idx];

  dt_iop_order_iccprofile_info_t *info = aligned_alloc(64, sizeof(dt_iop_order_iccprofile_info_t));
  memset(info, 0, sizeof(*info));
  info->type = type;
  static float lut[6][LUTSIZE];
  cmsHPROFILE prof = _create_profile(type);
  if(dt_colorspaces_get_matrix_from_input_profile(prof, info->matrix_in, lut[0], lut[1], lut[2], LUTSIZE) == 0
     && dt_is_valid_colormatrix(info->matrix_in[0][0])
     && dt_colorspaces_get_matrix_from_output_profile(prof, info->matrix_out, lut[3], lut[4], lut[5], LUTSIZE) == 0
     && dt_is_valid_colormatrix(info->matrix_out[0][0]))
  {
    transpose_3xSSE(info->matrix_in, info->matrix_in_transposed);
    transpose_3xSSE(info->matrix_out, info->matrix_out_transposed);
    dt_colorspaces_get_primaries_and_whitepoint_from_profile(prof, info->primaries, info->whitepoint);
  }
  else
  {
    fprintf(stderr, "perfil %d sin matriz\n", type);
    exit(1);
  }
  cmsCloseProfile(prof);
  profile_cache[idx] = info;
  return info;
}

const dt_iop_order_iccprofile_info_t *dt_ioppr_get_pipe_work_profile_info(dt_dev_pixelpipe_t *pipe)
{
  (void)pipe;
  // working profile por defecto de darktable: Rec2020 lineal
  return dt_ioppr_add_profile_info_to_list(NULL, DT_COLORSPACE_LIN_REC2020, "", DT_INTENT_PERCEPTUAL);
}

void dt_ioppr_get_export_profile_type(dt_develop_t *dev, dt_colorspaces_color_profile_type_t *type,
                                      const char **filename)
{
  (void)dev;
  // export profile por defecto de darktable: sRGB
  *type = DT_COLORSPACE_SRGB;
  *filename = "";
}

static void read_params(const char *path, dt_iop_agx_params_t *p)
{
  FILE *f = fopen(path, "r");
  if(!f) { perror(path); exit(1); }
  char name[128];
  double value;
  while(fscanf(f, "%127s %lf", name, &value) == 2)
  {
    int found = 0;
#define F(field, kind)                                                                             \
    if(!strcmp(name, #field)) { p->field = (#kind)[0] == 'f' ? (float)value : (int)value; found = 1; }
    AGX_FIELDS(F)
#undef F
    if(!found) { fprintf(stderr, "parametro desconocido: %s\n", name); exit(1); }
  }
  fclose(f);
}

static void print_params(const dt_iop_agx_params_t *p)
{
#define F(field, kind) printf("%s %.9g\n", #field, (double)p->field);
  AGX_FIELDS(F)
#undef F
}

static int preset(const char *name, dt_iop_agx_params_t *p)
{
  // misma secuencia que init_presets() en agx.c
  memset(p, 0, sizeof(*p));
  if(!strcmp(name, "scene-referred-default")) _set_scene_referred_default_params(p);
  else if(!strcmp(name, "unmodified-base-primaries")) _set_neutral_params(p);
  else if(!strcmp(name, "blender-like-base")) _set_blenderlike_params(p);
  else if(!strcmp(name, "blender-like-punchy")) { _set_blenderlike_params(p); _make_punchy(p); }
  else if(!strcmp(name, "sigmoid-like-default") || !strcmp(name, "sigmoid-like-smooth"))
  {
    _set_default_curve_and_look_params(p);
    _set_blenderlike_primaries(p);
    p->look_original_hue_mix_ratio = 1.0;
    p->curve_contrast_around_pivot = 3.07f;
    p->curve_toe_power = 1.40f;
    p->curve_shoulder_power = 3.71f;
    if(!strcmp(name, "sigmoid-like-smooth"))
    {
      _set_smooth_primaries(p);
      p->look_original_hue_mix_ratio = 0.f;
      p->curve_contrast_around_pivot = 2.98f;
      p->curve_toe_power = 1.61f;
      p->curve_shoulder_power = 3.02f;
    }
  }
  else if(!strcmp(name, "smooth")) _set_smooth_params(p);
  else return 0;
  return 1;
}

static float *read_f32(const char *path, size_t *n_pixels)
{
  FILE *f = fopen(path, "rb");
  if(!f) { perror(path); exit(1); }
  fseek(f, 0, SEEK_END);
  const long bytes = ftell(f);
  fseek(f, 0, SEEK_SET);
  *n_pixels = bytes / (3 * sizeof(float));
  float *rgb = malloc(bytes);
  if(fread(rgb, 1, bytes, f) != (size_t)bytes) { perror(path); exit(1); }
  fclose(f);
  return rgb;
}

static void print_matrix(const char *name, const dt_colormatrix_t m)
{
  printf("%s", name);
  for(int r = 0; r < 3; r++)
    for(int c = 0; c < 3; c++) printf(" %.9g", (double)m[r][c]);
  printf("\n");
}

int main(int argc, char **argv)
{
  if(argc == 5 && !strcmp(argv[1], "process"))
  {
    dt_iop_agx_params_t p;
    memset(&p, 0, sizeof(p));
    read_params(argv[2], &p);

    size_t n;
    float *rgb = read_f32(argv[3], &n);
    float *in = aligned_alloc(64, ((n * 4 * sizeof(float)) + 63) / 64 * 64);
    float *out = aligned_alloc(64, ((n * 4 * sizeof(float)) + 63) / 64 * 64);
    for(size_t k = 0; k < n; k++)
    {
      in[4 * k + 0] = rgb[3 * k + 0];
      in[4 * k + 1] = rgb[3 * k + 1];
      in[4 * k + 2] = rgb[3 * k + 2];
      in[4 * k + 3] = 1.f;
    }

    // commit_params()
    dt_iop_agx_data_t d;
    d.tone_mapping_params = _calculate_tone_mapping_params(&p);
    d.primaries_params = _get_primaries_params(&p);

    dt_develop_t dev;
    dt_dev_pixelpipe_t pipe;
    dt_iop_module_t self = { .dev = &dev };
    dt_dev_pixelpipe_iop_t piece = { .data = &d, .colors = 4, .pipe = &pipe };
    dt_iop_roi_t roi = { .width = (int)n, .height = 1 };
    process(&self, &piece, in, out, &roi, &roi);

    for(size_t k = 0; k < n; k++)
    {
      rgb[3 * k + 0] = out[4 * k + 0];
      rgb[3 * k + 1] = out[4 * k + 1];
      rgb[3 * k + 2] = out[4 * k + 2];
    }
    FILE *f = fopen(argv[4], "wb");
    fwrite(rgb, sizeof(float), 3 * n, f);
    fclose(f);
    return 0;
  }

  if(argc == 3 && !strcmp(argv[1], "preset"))
  {
    dt_iop_agx_params_t p;
    if(!preset(argv[2], &p)) { fprintf(stderr, "preset desconocido: %s\n", argv[2]); return 1; }
    print_params(&p);
    return 0;
  }

  if(argc == 2 && !strcmp(argv[1], "consts"))
  {
    const dt_iop_order_iccprofile_info_t *work = dt_ioppr_get_pipe_work_profile_info(NULL);
    const dt_colorspaces_color_profile_type_t types[] = { DT_COLORSPACE_LIN_REC2020, DT_COLORSPACE_DISPLAY_P3,
                                                          DT_COLORSPACE_ADOBERGB, DT_COLORSPACE_SRGB };
    const char *names[] = { "rec2020", "p3", "adobe", "srgb" };
    for(int k = 0; k < 4; k++)
    {
      const dt_iop_order_iccprofile_info_t *base
          = dt_ioppr_add_profile_info_to_list(NULL, types[k], "", DT_INTENT_RELATIVE_COLORIMETRIC);
      printf("%s primaries %.9g %.9g %.9g %.9g %.9g %.9g\n", names[k], base->primaries[0][0],
             base->primaries[0][1], base->primaries[1][0], base->primaries[1][1], base->primaries[2][0],
             base->primaries[2][1]);
      printf("%s whitepoint %.9g %.9g\n", names[k], base->whitepoint[0], base->whitepoint[1]);
      char label[64];
      snprintf(label, sizeof(label), "%s xyz_to_base_t", names[k]);
      print_matrix(label, base->matrix_out_transposed);
      // igual que en _create_matrices()
      dt_colormatrix_t pipe_to_base_transposed, base_to_pipe_transposed;
      dt_colormatrix_mul(pipe_to_base_transposed, work->matrix_in_transposed, base->matrix_out_transposed);
      mat3SSEinv(base_to_pipe_transposed, pipe_to_base_transposed);
      snprintf(label, sizeof(label), "%s pipe_to_base_t", names[k]);
      print_matrix(label, pipe_to_base_transposed);
      snprintf(label, sizeof(label), "%s base_to_pipe_t", names[k]);
      print_matrix(label, base_to_pipe_transposed);
    }
    return 0;
  }

  fprintf(stderr, "uso: dtref process <params> <in.f32> <out.f32> | preset <nombre> | consts\n");
  return 1;
}
