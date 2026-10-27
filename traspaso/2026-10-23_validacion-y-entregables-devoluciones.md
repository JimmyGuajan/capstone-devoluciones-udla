# Traspaso · Validación estadística, entregables y reportes

> **Nota (2026-10-26):** el pendiente sobre `equidad_destino.csv` quedó resuelto y la seudonimización ya está implementada. Ver [`2026-10-26_prototipo-final-punto-1-s10.md`](2026-10-26_prototipo-final-punto-1-s10.md).

**Fecha**: 2026-10-23
**Repositorio**: `capstone-devoluciones-udla` (privado según el propio chat; visibilidad no verificada)
**Rama**: `main` — todo el trabajo descrito está en `main`
**Commit al cerrar el trabajo**: `af30818`

> **Alcance de este traspaso.** La conversación fue larga y su primera parte quedó resumida por
> compactación de contexto. Esto cubre con detalle el tramo desde el commit `a64d557`
> (2026-09-19). Del tramo anterior solo se afirma lo que consta en el repositorio.

---

## 1. Propósito

Llevar el prototipo de predicción de devoluciones desde un primer modelo que no cumplía el criterio
comprometido hasta un modelo validado estadísticamente, y producir con él dos entregables
académicos y los reportes navegables que los acompañan.

---

## 2. Qué se hizo

54 archivos creados o modificados entre `a64d557` y `af30818`
(`git diff --name-status a64d557..HEAD`, 2026-10-23).

| Commit | Fecha | Qué entró |
|---|---|---|
| `8262c6d` | 2026-09-27 | `src/permanencia.py`, `src/antiguedad.py`, `sql/antiguedad.sql`, cuadernos 03 y 04, README |
| `822edc8` | 2026-09-28 | Tasa de conversión por marca (antes era una tasa global) |
| `02c9f1d` | 2026-09-28 | Horizonte, discrepancia abierta y objeción previsible, en conclusiones |
| `96c0fd0` | 2026-09-28 | Comparación al grano del criterio; desviación de grano declarada |
| `f91bb0a` | 2026-09-28 | Renombrado del modelo + verificación contra el GLM de `statsmodels` |
| `44654d0` | 2026-10-05 | Cuaderno 05 (trazabilidad de la decisión de modelado) |
| `ef515d3` | 2026-10-05 | `src/extension.py`, cuaderno 06, `cuadro_v6.csv`, `.gitignore` (+`data 3/`); **además** tres HTML que estaban sueltos en la raíz y entraron por `git add -A` |
| `daf022c` | 2026-10-11 | Cuaderno 07, `CHANGELOG.md`, README; los tres HTML pasan a `reports/html/` |
| `d941697` | 2026-10-11 | `docs/Ajustes_prototipo_y_validacion_Grupo5.docx` |
| `658f872`, `17c34c0`, `9b4f95f`, `799b2e1`, `7214b40`, `6a76d67` | 2026-10-11 | Correcciones del documento y del README tras revisión |
| `e4d2b6b` | 2026-10-11 | Merge de `ajustes-validacion` en `main` (PR #1, estado MERGED) |
| `58e0dd9` | 2026-10-11 | Cuaderno 08; documento de interpretabilidad y ética (docx + pdf) |
| `804cde4` | 2026-10-19 | `reports/html/` reorganizado: dos páginas vigentes, tres obsoletas retiradas |
| `af30818` | 2026-10-19 | Cifras de volumen corregidas en el reporte HTML del recorrido |

**Archivos principales** (verificado):

- `src/permanencia.py`, `src/antiguedad.py`, `src/extension.py`
- `notebooks/03` a `notebooks/08` (seis cuadernos nuevos)
- `docs/` — dos documentos de entrega, en Word y PDF
- `reports/html/` — dos páginas navegables + README
- `CHANGELOG.md`, `.claude/agents/revisor-entregables.md`
- **15 CSV** en `reports/` (conteo con `git ls-files reports/*.csv`, 2026-10-23)

---

## 3. Decisiones y alternativas descartadas

### 3.1 Modelo seleccionado: regresión de Poisson con offset de exposición

```
E[devoluciones] = unidades_en_riesgo × tasa_conversión(marca)
```

La tasa se reestima cada mes con los 9 anteriores y se encoge hacia la tasa global con k = 300.

**Descartados**: Random Forest y XGBoost, que son los que nombra el Objetivo Específico 3 del
capstone. Se entrenaron y se compararon; **cumplen el criterio por sí solos**. No se eligieron
porque el modelo de tasa gana sobre validación (jul–dic 2025). Se mantienen en todos los reportes.

**Por qué**: SHAP sobre ambos ensambles mostró que una sola variable concentra la predicción
(70,6 % en XGBoost, 94,2 % en Random Forest), de modo que dejó de cumplirse la condición bajo la
cual la literatura del capstone sitúa a los ensambles por delante.

### 3.2 Grano: marca × mes, no distribuidor × SKU

El OE3 enuncia «por distribuidor y SKU». Se midió la densidad de cada grano posible
**con un script ad hoc en el chat el 2026-10-19; ese cálculo no está en ningún cuaderno**:

| Grano | Series | Densidad |
|---|---:|---:|
| marca × mes | 11 | 68,0 % |
| ciudad × mes | 52 | 57,0 % |
| distribuidor × mes | 79 | 30,6 % |
| SKU × mes | 391 | 17,7 % |
| distribuidor × SKU × mes | 30.889 | **0,9 %** |

Se declara como desviación en el README y en el cuaderno 04, apoyada en el Plan Capstone v4 §5.7
(modelar en el nivel denso y desagregar top-down). **Ojo**: el README cita 61,6 % y 19,8 %
(cuaderno 02, definición antigua del objetivo); ver «Trampas».

### 3.3 Validación: walk-forward, no k-fold

Se descartó la validación cruzada clásica por producir fuga temporal. Se explica
expresamente en el documento de entrega, porque el enunciado de la tarea nombraba k-fold.

### 3.4 Ampliar la prueba sin tocar la selección

Al llegar la entrega complementaria (agosto y septiembre) se amplió **solo** el conjunto de
prueba. Entrenamiento y validación quedaron intactos.

### 3.5 Artefactos versionados por separado

`v2_*`, `v4_*`, `v6_*`, `v7_*`. Se descartó regenerar los antiguos para que los cuadernos previos
sigan siendo reproducibles tal como se ejecutaron.

---

## 4. Estado actual

### Funciona

- Los **ocho cuadernos** se ejecutan sin errores: 117 celdas de código, 117 ejecutadas, 0 errores
  *(lectura de los `.ipynb`, 2026-10-23)*
- Los dos documentos de entrega abren en Word y tienen 3 páginas cada uno *(PDF, 2026-10-23)*
- Las dos páginas HTML son autocontenidas
- `main` sincronizado con `origin`, sin cambios pendientes antes de crear este traspaso

### Cifras clave

Prueba = enero–septiembre de 2026.

| Métrica | Valor | Origen | Fecha |
|---|---:|---|---|
| MAPE del volumen mensual | **4,1 %** | `reports/metricas_v6.csv` | 2026-10-05 |
| MAE · RMSE | 41,0 · 69,9 | ídem | ídem |
| WMAPE (marca × mes) | 0,1161 | ídem | ídem |
| Random Forest · XGBoost (MAPE) | 5,2 % · 9,5 % | ídem | ídem |
| MAPE medio walk-forward (21 orígenes) | 5,26 % | `reports/walkforward.csv` | 2026-10-11 |
| IC 95 % bootstrap | [3,62 – 7,19] | `reports/ic_bootstrap.csv` | 2026-10-11 |
| Peor origen | 17,52 % | `reports/walkforward.csv` | 2026-10-11 |
| Dispersión de Pearson φ | 8,9 | cuaderno 07 | 2026-10-11 |
| Cobertura quasi-Poisson | 95,2 % | cuaderno 07 | 2026-10-11 |
| Validación del objetivo | 99,75 % (799/801) | cuadernos 04 y 05 | 2026-09-27 |
| SHAP de `en_riesgo` | 70,6 % XGB · 94,2 % RF | `reports/shap_dos_ensambles.csv` | 2026-10-11 |

### Volumen de datos

Calculado con scripts ad hoc en el chat el 2026-10-19 sobre los parquet `v6_*`.
**Ningún cuaderno lo reproduce.**

| | |
|---|---:|
| **Archivos que lee el código** (`Data tesis/` + `data 3/`) | 1.141 · 2,63 GB |
| · `Data tesis/` | 1.077 archivos · 2,43 GB |
| · `data 3/` | 64 archivos · 0,20 GB |
| Snapshots de inventario / consolidados de despachos | 1.075 / 35 |
| Filas de inventario | 14.007.314 |
| Filas de despachos | 6.383.678 |
| Estadías | 775.024 |
| Periodos de permanencia | 314.091 (258.299 con despacho) |
| Eventos (cruzan el umbral) | 39.798 |
| IMEI rastreados de punta a punta | 234.638 |
| Panel del modelo | 319 filas · 29 meses · 11 marcas |
| Entrenamiento / validación / prueba | 154 / 66 / 99 filas |

Carpetas presentes en el disco pero **no leídas por el código vigente**: `Data/` (122 archivos,
1,60 GB) y `Data2/` (81 archivos, 1,29 GB). Ver error nº 11.

---

## 5. Verificado / supuesto / no verificado

### Hecho y verificado

- Historial, archivos tocados y estado del repo *(`git log`, `git diff`, `git status`, 2026-10-23)*
- Los ocho cuadernos sin errores *(2026-10-23)*
- Cifras de la tabla «Cifras clave» contra sus CSV *(2026-10-23)*
- **El código solo lee `Data tesis/` y `data 3/`** *(`src/config.py` línea 6; `src/extension.py` línea 37; búsqueda sin coincidencias de `Data2`/`Data/` en `src/` y `notebooks/`, 2026-10-23)*
- Carpetas del cliente y `data/processed/` en `.gitignore`; **0 archivos `.parquet` rastreados** *(2026-10-23)*
- PR #1 en estado MERGED *(`gh pr list`, 2026-10-23)*
- Equivalencia con el GLM de Poisson de `statsmodels`: correlación 0,9991 *(cuadernos 04 y 05)*
- El PDF `docs/Interpretabilidad_y_etica_Grupo_5.pdf` coincide con el `.docx` actual; el PDF
  `docs/Interpretabilidad_y_etica_Grupo5.pdf` **no** (ver «Trampas») *(comparación de texto, 2026-10-23)*
- `docs/Ajustes_prototipo_y_validacion_Grupo5.pdf` contiene el texto vigente («Doce módulos»,
  «seiscientos») *(2026-10-23)*

### Supuesto

- Que `TIGO` y `MOVISTAR` son la misma operación tras un cambio de marca comercial. Lo confirmó el
  usuario en el chat; no hay documento del cliente que lo acredite en el repo.
- Que los 3.908 equipos despachados en agosto de 2026 son la cifra real. Coincide en dos entregas
  distintas, pero está un 37 % por debajo del promedio del año.
- Que `Data/` y `Data2/` son entregas anteriores del cliente, superadas por `Data tesis/`. Consta
  en el resumen del chat; no se puede comprobar en el repo.
- Que los dos PDF añadidos a `docs/` por fuera del asistente los exportó el usuario desde Word.
  No consta quién los generó.

### No verificado

- Que el repositorio sea privado en GitHub (el remoto coincide; la visibilidad no se comprobó).
- El uso de `src/warehouse.py`: no se ejecutó en este tramo; el almacén SQL puede estar
  desfasado respecto de los parquet actuales.
- La correlación 0,9991 con `PoissonRegressor` de `scikit-learn`: se calculó en un script ad hoc
  del chat y **no está en ningún cuaderno**. Solo la de `statsmodels` está en el repo.
- La tabla de densidades por grano (sección 3.2) y las cifras de volumen (sección 4): scripts ad
  hoc, no reproducibles desde el repo.
- El afirmado «sesgo sistemático» que producía una tasa global fija: no hay artefacto de esa
  variante en el repo.
- Si el contenido de `docs/Ajustes_prototipo_y_validacion_Grupo5.docx` cambió al re-guardarlo en
  Word. Su tamaño pasó de 16.653 a 16.810 y a 23.188 bytes entre commits; el texto cotejado
  coincide en las frases comprobadas, pero no se cotejó entero.

---

## 6. Errores cometidos y correcciones

Errores del asistente durante este chat, detectados y corregidos salvo indicación.

| # | Error | Cómo se detectó y corrigió |
|---|---|---|
| 1 | Selección de modelo mirando el conjunto de prueba (seis variantes) | Detectado por el asistente; rehecho con validación intermedia. Validación 5,3 % y prueba 5,0 % equivalentes |
| 2 | Agosto de 2026 excluido sin necesidad; se dijo que faltaba inventario | Al incorporar `data 3` se comprobó que ya estaba completo. Corregido en cuaderno 06 y README |
| 3 | Edición del README que falló en silencio (`└──` donde decía `├──`) | Árbol incompleto durante varios commits. Detectado por el agente revisor; corregido en `7214b40` |
| 4 | «HONOR concentra la mayor parte del error»: son 151 de 369, el 41 % | Verificado contra `cuadro_v6.csv`; reformulado |
| 5 | Conteo de archivos obsoleto (1.015 y 33) | Corregido a 1.075 y 35 |
| 6 | Documento Word que no abría (`AlignmentType` pasado como objeto) | Validador XSD de la herramienta docx; corregido |
| 7 | Cuarta página en blanco por el párrafo que Word exige tras una tabla final | Detectado al renderizar a PDF; resuelto |
| 8 | Cifras obsoletas en el HTML del recorrido (pasos 1 y 5) | Detectado por el usuario; corregido en `af30818` |
| 9 | «8,2 % de unidades no rastreables» venía de un artefacto del pipeline antiguo | Recalculado: 2,8 % (7.259 de 260.194). Corregido en `af30818` |
| 10 | Seis cifras erróneas en el documento de ajustes (commits, módulos, 400 vs 600 árboles, etc.) | Detectadas por el agente revisor; corregidas en `17c34c0` |
| 11 | **«5,5 GB en 1.344 archivos»** presentado al usuario como lo tratado. Incluye `Data/` y `Data2/`, que el código vigente no lee. Lo correcto es 1.141 archivos y 2,63 GB | Detectado al preparar este traspaso. **Sin corregir en el chat anterior**; el usuario debe usar la cifra de la sección 4 si le preguntan en la defensa |
| 12 | Se usó `git add -A` y entraron en commits del asistente archivos ajenos (dos PDF en `docs/` y el `.docx` de ética modificado) | Señalado al usuario en su momento; no se revirtió |

**Error del agente revisor, no del asistente**: marcó el MASE 0,098 como erróneo comparándolo con
`metricas_finales.csv` (evaluación de 7 meses). El 0,098 es correcto para la de 9. Verificado y
descartado.

**Errores de este mismo traspaso, corregidos antes de mostrarlo**: decía «nueve CSV» (son 15);
copiaba un IMEI literal en un ejemplo (retirado); atribuía a los cuadernos la comparación con
`PoissonRegressor` (es ad hoc); atribuía al cuaderno 08 la tabla de densidades (es ad hoc).

---

## 7. Pendientes, por orden de importancia

1. **`reports/equidad_destino.csv` publica 37 distribuidores con nombre** y su tasa de retención,
   versionado en git. Contradice la recomendación del propio documento de ética (seudonimizar).
   Pendiente de decisión del usuario: convertir a alias en el cuaderno 08 y regenerar.
2. **Scripts de construcción no versionados.** Los cuadernos 06, 07 y 08 leen `v6_*`/`v7_*`, que se
   construyen con scripts que se ejecutaron desde el directorio temporal de la sesión y **no están
   en el repo**. Si se borran los parquet, no se pueden reejecutar sin reescribir esos scripts.
3. **Capstone actualizado.** El usuario anunció que enviará una versión con objetivos modificados.
   Revisar las referencias al OE3 («por distribuidor y SKU») y al OE5 (ajuste de la demanda neta,
   hoy declarado fuera de alcance en el README).
4. **PDFs de ética.** Decidir cuál queda. El `Grupo_5` (del usuario) coincide con el `.docx` actual;
   el `Grupo5` (del asistente) está desactualizado.
5. **Seudonimización comprometida en el capstone y no implementada.** Los parquet locales conservan
   IMEI, ICCID y RUC en claro. Mitigado por `.gitignore` y repositorio privado; no resuelto.
6. **`Libro1.xlsx` no reproducido** (correlación −0,74 con la serie). A la espera de que el cliente
   explique cómo se generó.
7. **HTML desactualizados y sin versionar**: la memoria técnica y el explorador interactivo siguen
   con 7 meses de prueba; están publicados como artefactos, no en el repo.
8. **Almacén SQL Server sin recargar** (`python -m src.warehouse`).
9. **Agente `revisor-entregables`**: está en `.claude/agents/` pero solo se registra al iniciar una
   sesión nueva; en este chat se ejecutó con sus mismas instrucciones mediante un agente genérico.

---

## 8. Trampas conocidas

- **`31 meses` y `29 meses` son ambos correctos.** Serie completa 2024-03 → 2026-09 (31); el
  panel del modelo tiene 29 tras los rezagos.
- **Dos MAPE conviven**: 4,1 % (volumen mensual agregado, 9 meses de prueba) y 5,26 %
  (media de 21 orígenes del walk-forward). Poblaciones distintas.
- **A grano marca × mes el MAPE es 17,3 %**, no 4,1 %. El criterio del OE4 se fija sobre el
  agregado («MAPE agregado ≤ 15 %», Plan Capstone v4). Se reportan ambos.
- **Densidades en conflicto**: el README dice marca × mes 61,6 % y SKU × mes 19,8 % (cuaderno 02,
  definición antigua); la medición del 2026-10-19 da 68,0 % y 17,7 %. Ambas son legítimas para su
  definición; no mezclar.
- **264.233 IMEI frente a 260.194.** El primero (conteo de IMEI en el parquet de despachos, chat
  2026-10-11) incluye filas de todos los segmentos; el segundo son equipos del segmento EQUIPO
  (chat 2026-10-19).
- **La hoja del consolidado de septiembre se llama `TIGO`**, no `MOVISTAR`. `src/fuentes.py` fija
  el nombre y fallaría; `src/extension.py` identifica la hoja por sus columnas.
- **El IMEI llega como `float64` en los Excel** (número de 15 dígitos con sufijo `.0`).
  `_serie_digitos` lo maneja; un regex ingenuo de 14-16 dígitos no.
- **XGBoost con `count:poisson` necesita `base_score=1.0` explícito**, o devuelve una constante
  del orden de 1e13.
- **`shap` y `bottleneck` están compilados contra numpy 1.x.** Con numpy 2 imprimen un aviso en
  stderr que Jupyter pinta como error sin serlo. Los cuadernos bloquean `bottleneck`.
- **El cuaderno 01 debe ejecutarse antes que los demás**: genera los parquet que todos leen.
- **No regenerar los `.docx` desde scripts.** Los `.docx` del repo pueden contener ediciones
  manuales del usuario (el de ética tiene una frase añadida en el subtítulo que el script no
  tenía), y los scripts que los generan tampoco están versionados.
- **Windows no distingue mayúsculas**: un `cp` a `el_camino_hasta_el_modelo.html` sobrescribió
  `El_camino_hasta_el_modelo.html`.
- **`reports/metricas_v4.csv`, `metricas_finales.csv` y los `v2_*`/`v4_*`** corresponden a estados
  anteriores (7 meses de prueba); las vigentes son las `*_v6.csv`.

---

## 9. Reglas y preferencias fijadas por el usuario en este chat

- **No tocar `main` sin aviso**: pidió trabajar en rama aparte para poder volver atrás; la fusión
  se hizo cuando lo indicó.
- **Explicar antes de hacer.** En varias peticiones pidió expresamente *«explícame, no hagas
  cambios»* y *«explícame primero qué harás para ver si es lo que necesito»*.
- **Las carpetas de datos del cliente no se versionan nunca** (LOPDP: IMEI, ICCID, RUC,
  direcciones).
- **Alcance acotado a la predicción del volumen de devoluciones.** El ajuste de la demanda neta
  se retiró del README y de los documentos; permanece en los cuadernos 04 y 06 como cálculo derivado.
- **Solo equipos móviles**, no tarjetas SIM.
- **No sobrevender**: el usuario valoró que los entregables declaren las debilidades (ventaja no
  concluyente frente a Random Forest, un origen que incumple el umbral, sobredispersión).
- Preferencia por **documentos de 2–3 páginas** y por **PDF** cuando la tarea lo pide.
- Le interesa que las cifras resistan preguntas de defensa («me van a preguntar con cuánta data
  tratamos»).

---

## 10. Estado del repositorio

*(verificado 2026-10-23, antes de crear este traspaso)*

- **Rama actual**: `main`
- **Commits sin empujar**: 0
- **Archivos sin confirmar**: 0 (después: `traspaso/` nuevo, creado por este traspaso)
- **Ramas**: `main` y `ajustes-validacion` (ya fusionada; existe local y en remoto)
- **PR #1**: MERGED
- **Cambios ajenos**: ninguno pendiente. Durante el chat aparecieron en `docs/` dos PDF que el
  asistente no generó (`Ajustes_prototipo_y_validacion_Grupo5.pdf` e
  `Interpretabilidad_y_etica_Grupo_5.pdf`) y el `.docx` de ética modificado; entraron en commits
  del asistente por un `git add -A`.

---

## 11. Últimas diez peticiones del usuario, textuales

> La conversación es larga y su primera parte está resumida por compactación. Lo siguiente son las
> diez últimas, más recientes primero. Los saltos de línea se muestran con « / ».

| # | Petición textual | Qué se hizo |
|---|---|---|
| 1 | «Inténtalo de nuevo» | Se reintentó la comprobación de datos personales que había fallado por un error de escape; se completó la verificación del borrador |
| 2 | «Voy a migrar este proyecto a otro equipo de Claude y el contexto de ESTE chat tiene que quedar escrito en git. Haz un traspaso de este chat. Responde en español.» *(seguida de reglas y estructura de 12 puntos, no transcritas por extensión)* | Se redactó este archivo; sin commit ni push a la espera de OK |
| 3 | «sube esto al repo ya esta?» | Se verificó que ya estaba: local y remoto en `af30818` |
| 4 | «ok, actualiza el el camino hasta el modleo» | `af30818`: cifras corregidas; barrido de las 22 cifras de volumen |
| 5 | «ok y esto esta aclarado / esto teniamos en el camino hasta el modelo / creo que ese se hizo nates de agregr los 2 meses nuevos / puedes revisar / y no hagas cambios solo revisa» *(con captura)* | Revisión sin cambios: cuatro cifras obsoletas en los pasos 1 y 5 |
| 6 | «pero para el analsisi de lo que tenemos resultados usamos / no se basado en imes por anios y productos / cuanto fue por que me van a preguntar con cuanta data tratamos / y que usamos para entrar y predecir» | Desglose por año, por IMEI y por producto, y la partición de entrenamiento |
| 7 | «entonces para este analisis, no se uso millones de datos.. no / solo explicalo» | Se explicó que el modelo aprende de 154 filas y los millones construyen la variable |
| 8 | «cauntos datos se trato...podemos revisar... / dame una lista de cuanto hemos tratado» | Inventario de archivos, filas por etapa y entidades únicas (con el error nº 11 sin detectar aún) |
| 9 | «si guardalo en reports / y subelo al git» | `804cde4`: dos páginas versionadas, tres obsoletas retiradas |
| 10 | «Resultados ampliados a septiembre / donde esta este html» | Se localizó: publicado como artefacto y en carpeta temporal, fuera del repo |

---

## 12. Cómo retomar

### Qué leer, en este orden

1. `README.md` — definición del objetivo, resultados y desviaciones declaradas
2. `CHANGELOG.md` — ocho hitos
3. `notebooks/05_decision_modelo.ipynb` — **por qué** se eligió el modelo; incluye guion de defensa
4. `notebooks/06_extension_agosto_septiembre.ipynb` — resultado vigente (9 meses)
5. `notebooks/07_validacion_estadistica.ipynb` — walk-forward, bootstrap e incertidumbre
6. `notebooks/08_interpretabilidad_y_equidad.ipynb` — SHAP y sesgo geográfico
7. `docs/` — documentos de entrega

### Frase para pegar en un chat nuevo

> Proyecto capstone de predicción de devoluciones de inventario de equipos móviles (UDLA, Maestría
> en IA Aplicada). Lee primero `traspaso/2026-10-23_validacion-y-entregables-devoluciones.md`,
> después `README.md` y `CHANGELOG.md`. El modelo vigente es una regresión de Poisson con offset de
> exposición evaluada sobre enero–septiembre de 2026 (MAPE 4,1 %). Antes de afirmar cualquier cifra,
> verifícala contra los CSV de `reports/`, y desconfía de las cifras de volumen: no están
> respaldadas por ningún cuaderno.
