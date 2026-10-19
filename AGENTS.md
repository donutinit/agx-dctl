# agx-dctl: guía para agentes

El módulo AgX de darktable 5.6.2 (`src/iop/agx.c`) pasado a DCTL para DaVinci Resolve:
`AgX_darktable.dctl`. GPL-3.0-or-later, porque es obra derivada de darktable. `AGENTS.md` es el
archivo canónico y `CLAUDE.md` es un hard link.

## reglas

- El DCTL tiene que dar los mismos bits que darktable. Todo cambio a la matemática se valida con
  `python3 test/run.py` (la primera vez, `test/fetch.sh` baja darktable y lcms2). Si una prueba
  falla, no subas la tolerancia: encuentra la diferencia.
- La referencia (`test/dtref.c` y `test/extract.py`) usa el código de darktable tal cual, extraído
  por nombre de función. No reescribas a mano funciones de darktable en la referencia.
- El bloque entre `>>> generado` y `<<< generado` del DCTL lo escribe `test/gen_consts.py`. No se
  edita a mano.
- Las funciones del DCTL llevan el nombre de las de `agx.c` con prefijo `agx_` y el mismo orden de
  operaciones, y las matrices van transpuestas como `dt_colormatrix_t`. Por eso coincide bit a bit.
- DCTL: solo funciones de la documentación (`_floorf`, no `_floor`, que está deprecada), literales
  float con sufijo `f`, nada de doubles ni punteros, ningún nombre reservado de OpenCL o Metal, y
  los controles de UI solo se leen dentro de `transform()`. `test/compat.py` lo revisa y compila el
  archivo como OpenCL C y como C++.
- En lizeth no hay Resolve ni GPU. Lo que dependa de Resolve (que compile en la GPU, hacia dónde
  cuenta `p_Y`, el rendimiento) se lo pides a Diego. Para ver una imagen:
  `python3 test/render.py ~/.cache/agx-dctl/prueba.png p_show_curve=1`; nada pesado en `/tmp`, que
  vive en RAM.
- Textos en español sin rayas largas ni medias y con comillas rectas. El `.dctl` va en ASCII.
- Commits en español, de una línea, sin trailers.
