/* Corre el transform() del DCTL sobre pixeles float32 RGB.
 *
 *   dctl_run <params.txt> <entrada.f32> <salida.f32> [ancho alto]
 *
 * params.txt: lineas "p_nombre valor" con los controles del DCTL.
 * Sin ancho y alto, los pixeles van en una sola fila. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "build/dctl_gen.c"

static void set_param(const char *name, double value)
{
  for(ui_param_t *p = ui_params; p->name; p++)
  {
    if(strcmp(p->name, name)) continue;
    if(p->kind == 'f') *(float *)p->ptr = (float)value;
    else *(int *)p->ptr = (int)value;
    return;
  }
  fprintf(stderr, "control desconocido: %s\n", name);
  exit(1);
}

int main(int argc, char **argv)
{
  if(argc != 4 && argc != 6)
  {
    fprintf(stderr, "uso: dctl_run <params> <in.f32> <out.f32> [ancho alto]\n");
    return 1;
  }

  FILE *f = fopen(argv[1], "r");
  if(!f) { perror(argv[1]); return 1; }
  char name[128];
  double value;
  while(fscanf(f, "%127s %lf", name, &value) == 2) set_param(name, value);
  fclose(f);

  f = fopen(argv[2], "rb");
  if(!f) { perror(argv[2]); return 1; }
  fseek(f, 0, SEEK_END);
  const long bytes = ftell(f);
  fseek(f, 0, SEEK_SET);
  const size_t n = bytes / (3 * sizeof(float));
  float *rgb = malloc(bytes);
  if(fread(rgb, 1, bytes, f) != (size_t)bytes) { perror(argv[2]); return 1; }
  fclose(f);

  const int width = argc == 6 ? atoi(argv[4]) : (int)n;
  const int height = argc == 6 ? atoi(argv[5]) : 1;
  for(size_t k = 0; k < n; k++)
  {
    const float3 out = transform(width, height, (int)(k % width), (int)(k / width),
                                 rgb[3 * k], rgb[3 * k + 1], rgb[3 * k + 2]);
    rgb[3 * k] = out.x;
    rgb[3 * k + 1] = out.y;
    rgb[3 * k + 2] = out.z;
  }

  f = fopen(argv[3], "wb");
  fwrite(rgb, sizeof(float), 3 * n, f);
  fclose(f);
  return 0;
}
