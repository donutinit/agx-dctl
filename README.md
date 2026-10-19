# AgX de darktable para DaVinci Resolve

`AgX_darktable.dctl` es el módulo **AgX de darktable 5.6.2** pasado a DCTL: la misma matemática,
todos sus parámetros y los mismos presets, ahora para DaVinci Resolve. Recibe DaVinci Wide
Gamut / DaVinci Intermediate y sale listo para display (Rec.709 Gamma 2.4 por defecto).

No es "parecido a AgX": con la misma entrada da los mismos números que darktable. Eso está medido
contra el código de darktable compilado como C. En [Qué tan exacto es](#qué-tan-exacto-es) están
los resultados.

## Instalación

Necesitas **DaVinci Resolve Studio**: los DCTL no corren en la versión gratis.

1. En Resolve: Project Settings > Color Management > Lookup Tables > **Open LUT Folder**.
2. Copia ahí `AgX_darktable.dctl` y regresa a Resolve: **Update Lists**.
3. En la página Color agrega el efecto OpenFX **ResolveFX Color > DCTL** a un nodo y en "DCTL List"
   elige `AgX_darktable`.

Si cambias el archivo con Resolve abierto, el botón **Reload DCTL** del inspector lo recarga.

## Cómo armar el proyecto

AgX es tu transformación de display, así que va **al final** y Resolve no debe aplicar otra encima.
La forma más simple:

- Color science: **DaVinci YRGB** (sin color management).
- Timeline color space: **DaVinci WG/Intermediate**.
- Cada clip entra a DWG/Intermediate: con el decode de RAW o con un nodo Color Space Transform.
- `AgX_darktable` en el último nodo, o en un nodo de timeline para todo el proyecto.
- Output color space: **Rec.709 Gamma 2.4**, igual que el control `output` del DCTL.

Todo lo que corrijas antes del nodo de AgX trabaja en escena (DI), como en darktable los módulos
que van antes de AgX.

### Exposición

AgX espera el gris medio en 0.18 lineal, que en DaVinci Intermediate es **0.336** (344 en 10 bits).
El control `exposure before AgX` hace lo mismo que el módulo exposure de darktable. Ojo: darktable
sube **+0.7 EV** por defecto a los raw en el flujo scene-referred (`src/iop/exposure.c`), y Resolve
no. Si un raw te queda más oscuro que en darktable, empieza por ahí.

## Controles

Están en el mismo orden y con las mismas unidades que la interfaz de darktable: EV, porcentaje y
grados. Puedes copiar los valores de darktable tal cual.

**Extras del DCTL** (no existen en el módulo de darktable):

| Control | Qué hace |
|---|---|
| `preset` | "use sliders" (por defecto) usa los sliders. Cualquier otro preset ignora los sliders de AgX. |
| `input` | DaVinci Intermediate DWG, Linear DWG o Linear Rec.2020. |
| `exposure before AgX` | EV antes de AgX, como el módulo exposure de darktable. |
| `output` | Rec.709 Gamma 2.4, sRGB, Display P3, Rec.2020 Gamma 2.4 o Linear Rec.2020 (sin recorte ni codificación, para un CST después). |
| `show curve` | Dibuja la gráfica de la curva abajo a la izquierda, como "show curve" en darktable. |

**Settings** (configuración):

| DCTL | darktable (inglés) | darktable (español) | Unidad | Por defecto |
|---|---|---|---|---|
| `white relative exposure` | white relative exposure | exposición blanca relativa | EV | 6.5 |
| `black relative exposure` | black relative exposure | exposición negra relativa | EV | -10 |
| `pivot relative exposure` | pivot relative exposure | exposición relativa del punto medio | EV | 0 |
| `pivot target output` | pivot target output | salida de destino del punto medio | % | 18 |
| `contrast` | contrast | contraste | | 3 |
| `shoulder power` | shoulder power | potencia del tramo superior | | 3.3 |
| `toe power` | toe power | potencia del tramo inferior | | 1.5 |
| `look slope` | look > slope | apariencia > pendiente | | 1 |
| `look lift` | look > lift | apariencia > realce | | 0 |
| `look brightness` | look > brightness | apariencia > brillo | | 1 |
| `look saturation` | look > saturation | apariencia > saturación | % | 100 |
| `look preserve hue` | look > preserve hue | apariencia > preservación de tono | % | 60 |
| `shoulder start` | shoulder start | inicio del tramo superior | % | 0 |
| `target white` | target white | blanco destino | % | 100 |
| `toe start` | toe start | inicio del tramo inferior | % | 0 |
| `target black` | target black | negro destino | % | 0 |
| `keep the pivot on the diagonal` | keep the pivot on the diagonal | asegurar el punto medio en la diagonal | | no |
| `curve y gamma` | curve y gamma | curva y gamma | | 2.2 |

**Primaries** (colores primarios):

| DCTL | darktable (inglés) | darktable (español) | Unidad | Por defecto |
|---|---|---|---|---|
| `base primaries` | base primaries | colores primarios básicos | | Rec2020 |
| `disable adjustments` | disable adjustments | inhabilitar ajustes | | no |
| `red attenuation` | red attenuation | atenuación del rojo | % | 29.4625 |
| `red rotation` | red rotation | rotación del rojo | grados | 2.0285 |
| `green attenuation` | green attenuation | atenuación del verde | % | 25.8619 |
| `green rotation` | green rotation | rotación del verde | grados | -1.2081 |
| `blue attenuation` | blue attenuation | atenuación del azul | % | 14.6414 |
| `blue rotation` | blue rotation | rotación del azul | grados | -3.6129 |
| `reverse all` | reverse all | revertir todo | | no |
| `master purity boost` | master purity boost | acentuación de pureza general | % | 100 |
| `master rotation reversal` | master rotation reversal | rotación inversa general | % | 0 |
| `red purity boost` | red purity boost | acentuación del rojo | % | 29.0776 |
| `red reverse rotation` | red reverse rotation | rotación inversa del rojo | grados | 2.0285 |
| `green purity boost` | green purity boost | acentuación del verde | % | 26.3155 |
| `green reverse rotation` | green reverse rotation | rotación inversa del verde | grados | -1.2081 |
| `blue purity boost` | blue purity boost | acentuación del azul | % | 4.5811 |
| `blue reverse rotation` | blue reverse rotation | rotación inversa del azul | grados | -3.6129 |

Los valores por defecto son los del preset "scene-referred default", el que darktable aplica solo
cuando el flujo de trabajo es scene-referred (AgX).

Dos rangos son más cortos que en darktable para que el slider sirva: `look brightness` va de 0 a 10
(darktable deja hasta 100) y `curve y gamma` de 0.01 a 10 (darktable deja hasta 100). En darktable
el recorrido normal de esos sliders es de 0 a 2 y de 1 a 5.

## Presets

El control `preset` trae los siete de darktable:

| DCTL | darktable (inglés) | darktable (español) |
|---|---|---|
| scene-referred default | scene-referred default | basado en la escena (predefinido) |
| blender-like base | blender-like > base | estilo Blender > básico |
| blender-like punchy | blender-like > punchy | estilo Blender > intenso |
| sigmoid-like default | sigmoid-like > default | sigmoidal > predeterminado |
| sigmoid-like smooth | sigmoid-like > smooth | sigmoidal > suavizado |
| smooth | smooth | suavizado |
| unmodified base primaries | unmodified base primaries | colores primarios sin modificar |

Con un preset elegido, los sliders de AgX no hacen nada (sí funcionan `input`, `exposure before AgX`,
`output` y `show curve`). Para partir de un preset y moverlo, deja `preset` en "use sliders" y
escribe estos valores. Lo que no aparece es igual en todos y coincide con el valor por defecto:

| Control | scene-referred default | blender-like base | blender-like punchy | sigmoid-like default | sigmoid-like smooth | smooth | unmodified base primaries |
|---|---|---|---|---|---|---|---|
| `contrast` | 3 | 2.4535 | 2.4535 | 3.07 | 2.98 | 3 | 3 |
| `shoulder power` | 3.3 | 1.5 | 1.5 | 3.71 | 3.02 | 3.3 | 3.3 |
| `toe power` | 1.5 | 1.5 | 1.5 | 1.4 | 1.61 | 1.5 | 1.5 |
| `look brightness` | 1 | 1 | 0.5487 | 1 | 1 | 1 | 1 |
| `look saturation` | 100 | 100 | 140 | 100 | 100 | 100 | 100 |
| `look preserve hue` | 60 | 60 | 60 | 100 | 0 | 60 | 60 |
| `curve y gamma` | 2.2 | 2.4 | 2.4 | 2.2 | 2.2 | 2.2 | 2.2 |
| `red attenuation` | 29.4625 | 29.4625 | 29.4625 | 29.4625 | 10 | 10 | 0 |
| `red rotation` | 2.0285 | 2.0285 | 2.0285 | 2.0285 | 2 | 2 | 0 |
| `green attenuation` | 25.8619 | 25.8619 | 25.8619 | 25.8619 | 10 | 10 | 0 |
| `green rotation` | -1.2081 | -1.2081 | -1.2081 | -1.2081 | -1 | -1 | 0 |
| `blue attenuation` | 14.6414 | 14.6414 | 14.6414 | 14.6414 | 15 | 15 | 0 |
| `blue rotation` | -3.6129 | -3.6129 | -3.6129 | -3.6129 | -3 | -3 | 0 |
| `master purity boost` | 100 | 100 | 100 | 100 | 0 | 0 | 100 |
| `master rotation reversal` | 0 | 0 | 0 | 0 | 100 | 100 | 100 |
| `red purity boost` | 29.0776 | 29.0776 | 29.0776 | 29.0776 | 10 | 10 | 0 |
| `red reverse rotation` | 2.0285 | 2.0285 | 2.0285 | 2.0285 | 2 | 2 | 0 |
| `green purity boost` | 26.3155 | 26.3155 | 26.3155 | 26.3155 | 10 | 10 | 0 |
| `green reverse rotation` | -1.2081 | -1.2081 | -1.2081 | -1.2081 | -1 | -1 | 0 |
| `blue purity boost` | 4.5811 | 4.5811 | 4.5811 | 4.5811 | 15 | 15 | 0 |
| `blue reverse rotation` | -3.6129 | -3.6129 | -3.6129 | -3.6129 | -3 | -3 | 0 |

Los dos "smooth" usan en darktable el "working profile" como base; aquí es Rec2020, que es el
working profile por defecto de darktable. Los presets que quieras reusar guárdalos como PowerGrade.

## Lo que no se pudo pasar

Un DCTL calcula pixel por pixel y no puede medir el cuadro completo. Eso deja fuera:

- **Los goteros** (auto tune levels, los de white, black y pivot) y el botón de leer la exposición.
  En su lugar, mide en Resolve con el color picker o los scopes en DI y convierte con esta tabla
  (EV respecto al gris medio):

  | EV | DI (0 a 1) | DI (10 bits) |
  |---:|---:|---:|
  | -10 | 0.002 | 2 |
  | -8 | 0.007 | 8 |
  | -6 | 0.029 | 30 |
  | -4 | 0.093 | 95 |
  | -2 | 0.201 | 206 |
  | -1 | 0.267 | 273 |
  | 0 | 0.336 | 344 |
  | +1 | 0.407 | 417 |
  | +2 | 0.479 | 490 |
  | +3 | 0.552 | 565 |
  | +4 | 0.625 | 640 |
  | +5 | 0.698 | 714 |
  | +6 | 0.772 | 789 |
  | +6.5 | 0.808 | 827 |
  | +7 | 0.845 | 864 |
  | +8 | 0.918 | 939 |
  | +9 | 0.991 | 1014 |

  La fórmula exacta, con `v` el valor DI de 0 a 1 (arriba de 0.0274):
  `EV = log2((2^(v / 0.07329248 - 7) - 0.0075) / 0.18)`.
  Arriba del gris, cada EV son unos 0.073 en DI.
- **dynamic range scaling**: en darktable solo lo usan los goteros.
- **"export profile" y "working profile"** como base: elige el espacio directo. Por defecto en
  darktable son sRGB y Rec2020.
- **El botón "set from above"** (revertir y configurar): copia a mano attenuation a purity boost y
  rotation a reverse rotation, con los dos master en 100. O usa `reverse all`.
- **Máscaras y modos de fusión** del módulo: en Resolve se hacen con ventanas, keys y nodos.

## Qué tan exacto es

Las pruebas viven en `test/` y comparan el DCTL contra el AgX de darktable 5.6.2. La referencia no
es una reimplementación: `test/extract.py` copia tal cual las funciones de `agx.c` y de las
utilidades de color de darktable, y los perfiles de color salen de lcms2, igual que en darktable.
El `.dctl` se compila como C sin cambiar una línea y procesa la misma carta: rampa de grises de -16
a +16 EV, barrido de tonos dentro y fuera de gamut, 3000 colores al azar y casos raros (negativos,
NaN, infinito).

Resultado (diferencia máxima en salida lineal de display, de 0 a 1):

| Prueba | Diferencia |
|---|---|
| Los 7 presets | 0 (bit a bit) |
| 600 combinaciones de parámetros al azar (dos semillas), incluidos extremos | 0 (bit a bit) |
| Combo de presets contra sliders con los mismos valores | 0 |
| Entrada DaVinci Intermediate / DWG | 7e-7 (0 valores de código en 10 bits) |
| Salidas Rec.709, sRGB, Display P3 y Rec.2020 | 2e-7 |
| Matriz DWG a XYZ contra la que publica Blackmagic | 5e-9 |

**En GPU.** Resolve compila el DCTL para CUDA, OpenCL o Metal, y ahí `pow`, `log2` o `atan2` pueden
diferir unos ULP del resultado exacto. Simulando un error de hasta 4 ULP en cada una, los presets
quedan a **1 valor de código en 10 bits** de darktable; "unmodified base primaries" llega a 3 en
verdes fuera de gamut a +12 EV. Además `test/compat.py` compila el DCTL como OpenCL C 1.2 (clang) y
como C++14 (Metal es C++14) y revisa que solo use funciones de la documentación de DCTL.

**Lo que no depende del DCTL.** La misma entrada da la misma salida, pero lo que hace darktable antes
de AgX (demosaico, balance de blancos, color calibration, los +0.7 EV) no es lo que hace el decode de
Resolve. Una foto revelada en darktable y el mismo raw en Resolve van a diferir aunque AgX sea
idéntico, porque le llega otra imagen.

**darktable con ajustes extremos.** Con combinaciones raras (auto gamma alto, toe power de 8,
shoulder start alto) el AgX de darktable cambia aunque un parámetro se mueva en el último bit: en
una de las pruebas, mover el pivot 0.00000003 cambió la salida 0.04. Con ajustes normales no pasa.
Si copias valores de darktable, cópialos con todos sus decimales (clic derecho en el slider de
darktable para escribirlos).

**Por confirmar en Resolve** (no hay Resolve ni GPU en la máquina donde se armó):

- Que compile y corra en tiempo real en tu GPU. El DCTL recalcula la curva y las matrices en cada
  pixel; en GPU eso debería costar poco.
- Que la gráfica de `show curve` salga abajo a la izquierda y derecha. La documentación de DCTL no
  dice si `p_Y` cuenta desde arriba o desde abajo; el DCTL asume desde arriba. Si sale de cabeza, es
  un cambio de una línea en `agx_draw_curve`.

## Desarrollo

```sh
test/fetch.sh            # baja darktable 5.6.2 y lcms2 a test/upstream (fuera de git)
python3 test/run.py      # compila todo y corre las pruebas
python3 test/compat.py   # lint y compilación como OpenCL y C++
python3 test/render.py salida.png p_show_curve=1   # imagen de prueba renderizada con el DCTL
```

Necesita `cc`, `clang`, `g++`, `make`, `curl` y `python3`; nada de dependencias de Python.

- El bloque entre `>>> generado` y `<<< generado` del DCTL lo escribe `test/gen_consts.py`:
  primarios y matrices de los perfiles (de lcms2, como darktable), la matriz DWG a Rec2020 y los
  presets. No se edita a mano; `run.py` falla si no está al día.
- Para pasar a otra versión de darktable: cambia `DT_TAG` en `test/fetch.sh`, corre `fetch.sh`,
  revisa el diff de `agx.c`, porta los cambios al DCTL y corre `gen_consts.py` y `run.py`.

## Licencia

GPL-3.0-or-later, igual que darktable, porque el DCTL es obra derivada de `src/iop/agx.c`. Ver
`LICENSE`. AgX en darktable: darktable developers. AgX original: Troy Sobotka; la versión de
Blender, de la que salen los primarios "blender-like" y la compensación de gamut: Eary Chow.
