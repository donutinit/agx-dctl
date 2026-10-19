/* Las funciones de DCTL sobre C estandar, para correr el .dctl en CPU.
   Lo usa build/dctl_gen.c, que arma test/dctl2c.py. */
#pragma once
#include <math.h>

typedef struct { float x, y; } float2;
typedef struct { float x, y, z; } float3;

static inline float2 make_float2(float x, float y)
{
  float2 v = { x, y };
  return v;
}

static inline float3 make_float3(float x, float y, float z)
{
  float3 v = { x, y, z };
  return v;
}

#define __DEVICE__ static inline
#define __CONSTANT__ static const

#define _fabs fabsf
#define _fmaxf fmaxf
#define _fminf fminf
#define _floorf floorf
#define _ceilf ceilf
#define _round roundf

#ifndef AGX_NOISY_MATH
#define _powf powf
#define _logf logf
#define _log2f log2f
#define _log10f log10f
#define _exp2f exp2f
#define _expf expf
#define _sqrtf sqrtf
#define _hypotf hypotf
#define _cosf cosf
#define _sinf sinf
#define _atan2f atan2f
#else
/* Simula una GPU: cada funcion trascendental se equivoca hasta AGX_NOISY_MATH ulp,
   al azar pero de forma reproducible. */
static unsigned int agx_noise_state = 12345u;
static inline float agx_noisy(float r)
{
  agx_noise_state ^= agx_noise_state << 13;
  agx_noise_state ^= agx_noise_state >> 17;
  agx_noise_state ^= agx_noise_state << 5;
  const float u = (float)(agx_noise_state & 0xffffff) / (float)0xffffff * 2.0f - 1.0f;
  return r * (1.0f + u * (float)AGX_NOISY_MATH * 1.19209290e-7f);
}
#define _powf(x, y) agx_noisy(powf(x, y))
#define _logf(x) agx_noisy(logf(x))
#define _log2f(x) agx_noisy(log2f(x))
#define _log10f(x) agx_noisy(log10f(x))
#define _exp2f(x) agx_noisy(exp2f(x))
#define _expf(x) agx_noisy(expf(x))
#define _sqrtf(x) agx_noisy(sqrtf(x))
#define _hypotf(x, y) agx_noisy(hypotf(x, y))
#define _cosf(x) agx_noisy(cosf(x))
#define _sinf(x) agx_noisy(sinf(x))
#define _atan2f(y, x) agx_noisy(atan2f(y, x))
#endif
