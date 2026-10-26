# Predicción de devoluciones de inventario de equipos móviles

Capstone — Maestría en Inteligencia Artificial Aplicada, Universidad de Las Américas.
Grupo 5: Guaján Perugachi Jimmy Israel · Martínez Ortega Jorge Washington · Vásquez Chávez Marco Vinicio.

Predice el volumen mensual de devoluciones de equipos móviles por marca en un operador de
telefonía con presencia en Ecuador.

**Alcance.** El proyecto cubre la **predicción del volumen de devoluciones**. El ajuste de la
demanda neta, que en los cuadernos 04 y 06 aparece como cálculo derivado, queda fuera del alcance
de esta fase.

## Definición del target

```
DEVOLUCIÓN := unidad que cumple 60 días desde su fecha de despacho y sigue
              en poder del canal al cierre del mes
GRANO      : marca × mes      VENTANA: 2024-05 a 2026-09 (29 meses de panel)
```

Es la definición que usa el área de planificación del cliente, con tres reglas que se verificaron
una por una contra listados reales:

1. **Los días se cuentan desde la fecha de despacho**, no desde que la unidad aparece en el
   inventario del local. Verificado en 801 de 801 registros.
2. **El reloj no se reinicia al mover la unidad entre locales del canal.** Solo se reinicia si
   vuelve a bodega central y sale de nuevo.
3. **Es un flujo, no una fotografía.** Cada unidad se cuenta una sola vez: el mes en que cruza el
   umbral. Las que ya lo cruzaron antes no se repiten.

Se construye cruzando el reporte de **despachos** (cuándo salió cada IMEI y a dónde) con los
**snapshots diarios de inventario** (dónde está cada IMEI cada día). Contrastado contra el listado
de enero de 2025 entregado por el negocio: **99,75 % de coincidencia** (799 de 801 equipos).

## El pipeline

```
Data tesis/ (crudo, hasta jul-2026)            data 3/ (entrega complementaria, ago–sep 2026)
   │ src/fuentes.py · src/sources.py                │ src/extension.py
   ▼                                                 ▼
v2_stock · v2_despachos · fact_ventas ──────────► v6_stock · v6_despachos
   │ scripts/construir_v2.py                         │ scripts/construir_v6.py
   ▼                                                 ▼
v2_estadias · v2_ciclo_unidad                  v6_estadias ─► v6_periodos ─► v6_panel_modelo
   │ cuadernos 01–05: definición del target,                                    │
   ▼  primeros modelos y decisión                              ┌────────────────┴──────────────┐
                                                scripts/walk_forward.py        scripts/entrenar_y_evaluar.py
                                                       │ v7_walkforward               │ modelo/modelo_final.json
                                                       ▼                              ▼
                                           cuadernos 06 · 07 · 08            scripts/predecir.py (demo)
```

En una frase: del **inventario diario** y los **despachos** se obtienen los tramos donde estuvo cada
equipo (*estadías*), de ahí su permanencia en el canal (*periodos*) y, contando las unidades que
cumplen 60 días cada mes, el **panel marca × mes** sobre el que se entrena y se evalúa el modelo.

Volumen que recorre el código (medido sobre los artefactos de esta versión):

| Etapa | Filas |
|---|---:|
| Inventario diario (snapshots) | 14.007.314 |
| Despachos (equipos y SIM) | 6.383.678 |
| Estadías (tramos unidad × bodega) | 775.024 |
| Periodos de permanencia en canal | 314.091 (258.299 con despacho asociado) |
| Eventos que cumplen 60 días | 39.798 |
| **Panel marca × mes** | **319** (11 marcas · 29 meses · 16 columnas) |

El modelo no ve los 14 millones de filas: ve el panel de 319 filas, que las resume. La trazabilidad
completa está en [`reports/html/el_camino_hasta_el_modelo.html`](reports/html/el_camino_hasta_el_modelo.html).

## Estructura

```
├── Data tesis/ · Data/ · Data2/ · data 3/   entregas del cliente (no versionadas)
├── data/processed/             parquet generado por los scripts y cuadernos — no versionado
├── src/
│   ├── config.py               rutas, umbral, marcas, ventana limpia
│   ├── parsers.py              limpieza de tipos y convenciones de fecha
│   ├── fuentes.py              lectores de despachos y snapshots
│   ├── sources.py              lectores de ventas y catálogos
│   ├── ciclo.py                estadías y ciclo de vida por unidad
│   ├── antiguedad.py           segunda definición (días en la misma bodega)
│   ├── permanencia.py          definición final del target, confirmada con el negocio
│   ├── extension.py            lector de la entrega complementaria (hoja TIGO)
│   ├── panel_modelo.py         estadías → periodos → panel marca × mes
│   ├── modelo_final.py         modelo seleccionado, evaluación en prueba, modelo guardado
│   ├── validacion.py           walk-forward y líneas base
│   ├── modelo.py               baselines, métricas, RF y XGBoost
│   ├── artefactos.py           guardar o verificar un artefacto sin sobrescribirlo
│   ├── seudonimizar.py         seudonimización de identificadores (HMAC-SHA256)
│   ├── panel.py · events.py    utilidades de panel y eventos
│   └── warehouse.py            carga a SQL Server
├── scripts/
│   ├── construir_v2.py         estadías y ciclo por unidad
│   ├── construir_v6.py         extensión ago–sep y panel del modelo
│   ├── walk_forward.py         validación walk-forward y líneas base
│   ├── entrenar_y_evaluar.py   entrena, evalúa en la prueba y guarda el modelo
│   ├── predecir.py             demo: predicción de un mes con su intervalo
│   └── seudonimizar_artefactos.py · verificar_equivalencia.py
├── notebooks/
│   ├── 01_limpieza_y_eda.ipynb              limpieza, estadías y paneles
│   ├── 02_modelo.ipynb                      primer modelo — trazabilidad
│   ├── 03_antiguedad_inventario.ipynb       validación contra los reportes del negocio
│   ├── 04_modelo_final.ipynb                modelo final
│   ├── 05_decision_modelo.ipynb             por qué se eligió ese modelo
│   ├── 06_extension_agosto_septiembre.ipynb entrega complementaria
│   ├── 07_validacion_estadistica.ipynb      walk-forward, bootstrap e incertidumbre
│   └── 08_interpretabilidad_y_equidad.ipynb SHAP y auditoría de trato por territorio
├── modelo/modelo_final.json    el modelo entrenado: tasas por marca, ventana, k y φ
├── tests/                      33 pruebas (modelo, ausencia de fuga, seudonimización)
├── sql/                        consultas.sql · antiguedad.sql
├── docs/                       informes de entrega (Word y PDF) · solicitud de datos · muestra/
├── reports/                    métricas en CSV, figuras y reportes HTML navegables
├── CHANGELOG.md                bitácora del proyecto
└── .claude/agents/             agente de revisión de entregables
```

## Instalación

Requiere **Python 3.12** (se verificó con 3.12.4) y las versiones exactas de `requirements.txt`:

```bash
python -m venv .venv
.venv\Scripts\activate            # en Linux o macOS: source .venv/bin/activate
pip install -r requirements.txt
```

| Paquete | Versión | Para qué |
|---|---|---|
| `pandas` · `numpy` | 2.2.3 · 2.0.2 | manipulación y cálculo |
| `pyarrow` | 25.0.0 | caché en parquet |
| `scikit-learn` | 1.9.0 | Random Forest y utilidades |
| `xgboost` | 2.1.3 | XGBoost con objetivo Poisson |
| `statsmodels` | 0.14.4 | GLM de Poisson de referencia |
| `shap` | 0.52.0 | explicabilidad |
| `python-calamine` · `openpyxl` | 0.8.2 · 3.1.5 | lectura de Excel (calamine es unas 6 veces más rápida) |
| `matplotlib` | 3.11.1 | figuras |
| `duckdb` | 1.5.5 | consultas sobre parquet |
| `nbformat` · `nbconvert` · `ipykernel` | 5.11.1 · 7.17.1 · 6.29.5 | ejecutar los cuadernos |
| `pytest` | 8.3.5 | pruebas |

## Ejecución paso a paso

Los datos del cliente **no están en el repositorio** (ver «Datos personales»). Con ellos en
`Data tesis/` y `data 3/`, se reconstruye todo así. Cada script escribe su resultado en
`data/processed/` y, si ya existe, **lo compara en lugar de sobrescribirlo**: volver a ejecutar es una
prueba de reproducibilidad, no un riesgo para los resultados (`--forzar` reemplaza).

| Paso | Comando | Produce | Tiempo* |
|---|---|---|---:|
| 1 | `python scripts/construir_v2.py` | `v2_estadias`, `v2_ciclo_unidad` | 36 s |
| 2 | cuadernos **01 a 05** (ver abajo) | paneles v2–v4, primeros modelos y la decisión | — |
| 3 | `python scripts/construir_v6.py` | `v6_stock`, `v6_despachos`, `v6_estadias`, `v6_periodos`, `v6_panel_modelo` | 176 s |
| 4 | cuaderno **06** | entrega complementaria, prueba de 9 meses | — |
| 5 | `python scripts/walk_forward.py` | `v7_walkforward` y `reports/walkforward_con_lineas_base.csv` | 19 s |
| 6 | cuadernos **07** y **08** | validación estadística; SHAP y equidad | — |
| 7 | `python scripts/entrenar_y_evaluar.py` | evaluación en la prueba y `modelo/modelo_final.json` | 2 s |
| 8 | `python scripts/predecir.py --mes 2026-09` | la demo | 1 s |
| 9 | `python -m pytest tests` | 33 pruebas | 22 s |

\* Medidos con los parquet de entrada ya generados. La primera lectura de los archivos crudos
(1.141 archivos, 2,6 GB) es la parte lenta y la hace `src/fuentes.py` una sola vez: queda en caché.

Para ejecutar un cuaderno sin abrir Jupyter:

```bash
python -m nbconvert --to notebook --execute --inplace notebooks/07_validacion_estadistica.ipynb
```

Conviene usar `python -m nbconvert` y no `jupyter nbconvert`: el primero ejecuta el cuaderno con el mismo
intérprete del entorno virtual. En máquinas con Anaconda instalado, `jupyter` puede resolver al de
Anaconda y cargar paquetes ajenos (por ejemplo un `numexpr` compilado para NumPy 1.x, que pandas
importa solo y llena de avisos la primera celda).

| Cuaderno | Qué hace |
|---|---|
| `01_limpieza_y_eda` | limpieza, estadías y paneles v2 |
| `02_modelo` | primer modelo; se conserva como trazabilidad |
| `03_antiguedad_inventario` | validación contra los listados del negocio |
| `04_modelo_final` | modelo final, Objetivos 3 y 4 |
| `05_decision_modelo` | por qué se eligió ese modelo |
| `06_extension_agosto_septiembre` | entrega complementaria, prueba de 9 meses |
| `07_validacion_estadistica` | walk-forward, bootstrap e incertidumbre |
| `08_interpretabilidad_y_equidad` | SHAP y auditoría de equidad por ciudad y distribuidor |

### Probarlo sin los datos del cliente

La carpeta [`docs/muestra/`](docs/muestra/README.md) trae el panel marca × mes completo (319 filas, solo
totales, sin identificadores). Con él se puede ejecutar la demo y todas las pruebas:

```bash
python scripts/predecir.py --mes 2026-09 --panel docs/muestra/panel_modelo_muestra.csv
python -m pytest tests
```

## Demo: predecir un mes

```bash
python scripts/predecir.py --mes 2026-09
```

```
Mes 2026-09: tasas estimadas con los 9 meses anteriores, k=300

   marca  en_riesgo  tasa  prediccion
   APPLE        377 0.790       298.0
   HONOR        109 0.659        71.8
MOTOROLA        140 0.788       110.3
 SAMSUNG        402 0.735       295.7
  XIAOMI        160 0.728       116.4

  Prediccion del mes : 892 unidades
  Intervalo 95 %     : 718 a 1,066   (φ = 8.86)
  Lo ocurrido        : 899 unidades   (error -0.8 %, dentro del intervalo)
```

Para un mes futuro se entregan las unidades en riesgo de cada marca (CSV `marca,en_riesgo`; ejemplo en
`docs/muestra/en_riesgo_ejemplo.csv`) y se aplican las tasas guardadas en `modelo/modelo_final.json`:

```bash
python scripts/predecir.py --en-riesgo docs/muestra/en_riesgo_ejemplo.csv
```

## Pruebas

`python -m pytest tests` ejecuta 33 pruebas, todas con el panel de muestra o datos sintéticos:

- **Lógica del estimador:** el encogimiento acerca las tasas a la global, una marca sin historia usa la
  global, la ventana descarta lo antiguo, la predicción es unidades en riesgo × tasa.
- **Sin fuga de información:** los rezagos del panel son exactamente los meses anteriores, y una prueba
  de perturbación sobre `construir_panel` cambia lo que ocurre en el último mes y comprueba que ninguna
  variable explicativa de ese mes ni de los anteriores se mueve. Se comprobó que detecta tres fugas
  inyectadas a propósito.
- **Reproduce lo reportado:** MAPE 4,1 % / MAE 41,0 / RMSE 69,9 / WMAPE 0,1161 en la prueba; Random Forest
  5,2 % y XGBoost 9,5 %; walk-forward 5,26 % con peor origen 17,52 %.
- **Seudonimización:** determinismo, sin colisiones en 50.000 valores, uniones entre tablas conservadas.

Random Forest se compara con tolerancia (el paralelismo no garantiza igualdad bit a bit; la diferencia
medida es del orden de 10⁻¹³). XGBoost es idéntico al bit entre ejecuciones.

## Resultado

Entrenamiento con mayo 2024 – diciembre 2025, prueba sobre **enero–septiembre de 2026** en el
panel marca × mes. La selección entre modelos se hace sobre un conjunto de validación intermedio
(jul–dic 2025); el de prueba no interviene en ninguna decisión.

El Objetivo 4 fija el criterio sobre el **volumen mensual** (Plan v4: *«MAPE agregado ≤ 15 %»*):

| Modelo | MAPE mensual | MAE | RMSE | ¿Cumple ≤ 15 %? |
|---|---:|---:|---:|:--|
| **Tasa de conversión** | **4,1 %** | **41,0** | **69,9** | sí |
| Random Forest | 5,2 % | 49,0 | 63,6 | sí |
| XGBoost Poisson | 9,5 % | 76,4 | 89,7 | sí |

**Se cumple el MAPE ≤ 15 % comprometido en el Objetivo 4**, y los tres modelos lo cumplen por su
cuenta. A nivel de celda marca × mes el MAPE es mayor (17,3 %) porque unas pocas celdas de menos
de cinco unidades disparan el porcentaje; por eso se reporta WMAPE en paralelo (0,116).

El modelo ganador es una **regresión de Poisson con offset de exposición**:

```
E[devoluciones] = unidades_en_riesgo × tasa_conversión(marca)
```

La tasa se reestima cada mes con los 9 anteriores y se encoge hacia la tasa global con peso
k = 300. El cuaderno 04 verifica la equivalencia con el GLM de `statsmodels`: correlación 0,9991.

### Validación estadística

Validación **walk-forward** de 21 orígenes (cuaderno 07), que es el equivalente correcto a la
validación cruzada en series temporales:

| Modelo | MAPE medio | IC 95 % (bootstrap) | Peor origen |
|---|---:|---|---:|
| **Tasa de conversión** | **5,26 %** | [3,62 – 7,19] | 17,5 % |
| Random Forest | 7,17 % | [5,21 – 9,36] | 23,4 % |
| XGBoost Poisson | 10,56 % | [7,60 – 13,73] | 28,1 % |
| Naive (mes anterior) | 34,96 % | [22,28 – 54,01] | 196,1 % |

Dos referencias más simples, ejecutadas con el mismo walk-forward (`scripts/walk_forward.py`,
resultado en `reports/walkforward_con_lineas_base.csv`): la **media móvil de 3 meses** de cada marca
da un MAPE medio de **41,18 %**, y no anticipar ninguna devolución («cero») da **100 %**. El modelo
elegido las mejora en un factor de 8 y 19 respectivamente.

Dos matices que conviene leer: el intervalo del modelo elegido **se solapa con el de Random
Forest**, de modo que su ventaja es consistente pero no estadísticamente concluyente; y **1 de
los 21 orígenes supera el 15 %**, así que el criterio se cumple de media y en el periodo de
prueba, no en todos los meses posibles.

La dispersión de Pearson da **φ = 8,9**: hay sobredispersión de factor 9 frente al supuesto de
Poisson puro, cuyos intervalos cubrirían solo el 57 %. Corregidos (*quasi-Poisson*) la cobertura
sube al 95,2 %, y permiten reportar cada mes como un rango —por ejemplo, septiembre entre 718 y
1.066 unidades— en vez de un valor puntual.

### Qué cambió respecto de `02_modelo`

| | `02_modelo` | actual |
|---|---:|---:|
| Meses de prueba | 4 | 9 |
| WMAPE (marca × mes) | 0,401 | **0,116** |
| MAPE del volumen mensual | 28,3 % | **4,1 %** |
| Validación contra el negocio | ninguna | 99,75 % |

Cuatro correcciones: la definición del target no era la del negocio; faltaba la variable
predictora principal; el histórico estaba recortado por una dependencia innecesaria del reporte
de ventas; y el modelo se elegía mirando el conjunto de prueba.

## Una desviación declarada

El Objetivo 3 enuncia la estimación «por distribuidor y SKU», y el modelo trabaja por **marca ×
mes**. Medido en el cuaderno 02, marca × mes tiene el 61,6 % de las celdas con dato y SKU × mes
apenas el 19,8 %: con 269 SKU y 45 distribuidores salen unas 12.000 series casi todas en cero. El
Plan v4 §5.7 ya contemplaba modelar en el nivel denso y desagregar top-down, y es además el grano
que pide planificación.

## Decisiones de datos que hay que conocer

- **Se excluye el 17,8 % de los periodos** (55.792 de 314.091) por no tener despacho asociado: son
  unidades que ya estaban en tienda cuando arranca el histórico, o cuyo IMEI no aparece en ningún
  despacho. Incluirlas usando la fecha de llegada infla los primeros meses de la serie.
- **Octubre de 2026 en adelante queda fuera de la evaluación.** Con inventario hasta el 30 de
  septiembre, una unidad despachada el 2 de agosto cumple 60 días el 1 de octubre y ya no se
  puede observar. Agosto y septiembre sí son medibles gracias a la entrega complementaria
  (cuaderno 06).
- **Noviembre de 2025 tiene 4 días de inventario de 30.** Afecta el cálculo de antigüedad de las
  unidades que llegaron en ese período.
- **El alcance son los equipos móviles con IMEI**, que es la unidad trazable a lo largo de toda la
  cadena: despacho, inventario diario y permanencia en el canal. Sobre esa base se construyen el
  objetivo y las métricas.
- **El error se concentra en julio de 2026**, que aporta 193 de las 369 unidades de error de los
  nueve meses. Dentro de julio, HONOR pone 151. El diagnóstico de los cuadernos 06 y 07 apunta a
  una causa única y repetida en los tres meses analizados a fondo: un modelo de equipo recién
  lanzado, despachado en volumen, que no rota en sus primeros sesenta días. En septiembre fueron
  171 iPhone 17 Pro de los que se quedaron 169.
- **Qué pediríamos al cliente para cerrarlo.** No el modelo de equipo en sí, que deja de existir al
  descontinuarse, sino atributos que persisten entre generaciones: fecha de lanzamiento al
  catálogo, precio y gama, y calendario de acciones comerciales.
- **El modelo presenta un sesgo geográfico medido** (cuaderno 08). Asigna la tasa de la marca sin
  mirar el destino, y eso subestima entre 10 y 13 puntos a las ciudades intermedias —Machala
  +0,134, Ambato +0,117— frente a Quito y Guayaquil, que quedan en −0,02. El MAPE agregado del
  4,1 % no lo revela. Mientras no se incorpore el destino como dimensión, conviene reportar el
  error desagregado y no usar la predicción para evaluar al canal.
- **La tasa de conversión es empírica y se reestima cada mes.** El modelo se adapta solo a cambios
  del canal, pero un cambio brusco tarda un par de meses en absorberse.

## Datos personales y seudonimización

Los datos del cliente contienen IMEI, ICCID, RUC y nombres de bodegas y distribuidores, y están
sujetos a la Ley Orgánica de Protección de Datos Personales. **Nunca se versionan**: `.gitignore`
excluye las carpetas de entrega, los parquet y los CSV de datos, y el repositorio solo contiene
código, métricas agregadas y el panel de muestra (totales por marca y mes).

`src/seudonimizar.py` sustituye los identificadores (IMEI, ICCID, serie, RUC y los destinos) por
códigos con HMAC-SHA256 y una clave secreta que **no** se guarda en el repositorio. Los códigos son
deterministas, así que las uniones entre tablas se conservan, y el tipo de RUC (persona natural o
sociedad) se calcula antes de perder el dato. Para saber si altera algún resultado:

```bash
python scripts/seudonimizar_artefactos.py     # escribe a data/seudonimizado/, nunca sobre los originales
python scripts/verificar_equivalencia.py      # 13 comprobaciones: mismos periodos, panel y MAPE
```

**Estado:** el módulo está implementado y la equivalencia verificada (13 de 13, diferencia 0,00 en el
panel y el MAPE) con una clave de prueba. Aplicarlo a los artefactos del equipo con la clave definitiva
es una operación local, porque la clave no viaja con el código. Los nombres de bodega quedan en claro
en esta fase: la clasificación central/canal depende de ellos.

## Evidencias de validación y anexos

| Qué se quiere comprobar | Dónde está |
|---|---|
| Métricas finales en el periodo de prueba | [`reports/metricas_v6.csv`](reports/metricas_v6.csv) · se reproducen con `scripts/entrenar_y_evaluar.py` |
| Predicción mes a mes frente a lo real | [`reports/cuadro_v6.csv`](reports/cuadro_v6.csv) |
| Comparativa entre modelos y por qué se eligió el ganador | [`reports/decision_modelo.csv`](reports/decision_modelo.csv) · cuaderno `05_decision_modelo` (es el corte de la decisión, con 7 meses de prueba: las cifras finales con 9 meses son las de `metricas_v6.csv`) |
| Robustez: walk-forward, intervalos de confianza, cobertura | [`reports/walkforward.csv`](reports/walkforward.csv) · [`ic_bootstrap.csv`](reports/ic_bootstrap.csv) · [`intervalos_prueba.csv`](reports/intervalos_prueba.csv) · [`walkforward_con_lineas_base.csv`](reports/walkforward_con_lineas_base.csv) |
| Qué variables pesan en cada modelo (SHAP) | [`reports/shap_dos_ensambles.csv`](reports/shap_dos_ensambles.csv) · cuaderno `08` |
| Equidad por ciudad y distribuidor | [`reports/equidad_ciudad.csv`](reports/equidad_ciudad.csv) · [`reports/equidad_destino.csv`](reports/equidad_destino.csv) |
| Pruebas automáticas | `python -m pytest tests` — 33 pruebas |
| Resultados enero–septiembre de 2026, navegables | [`reports/html/resultados_ene-sep_2026.html`](reports/html/resultados_ene-sep_2026.html) |
| Cómo se llegó al modelo, paso a paso | [`reports/html/el_camino_hasta_el_modelo.html`](reports/html/el_camino_hasta_el_modelo.html) |
| Ajustes y validación del prototipo (informe) | [`docs/Ajustes_prototipo_y_validacion_Grupo5.pdf`](docs/Ajustes_prototipo_y_validacion_Grupo5.pdf) |
| Interpretabilidad y ética (informe) | [`docs/Interpretabilidad_y_etica_Grupo5.docx`](docs/Interpretabilidad_y_etica_Grupo5.docx) |
| Historia de los cambios | [`CHANGELOG.md`](CHANGELOG.md) · historial de Git |

## Control de versiones

Git, con la rama `main` como línea estable. `CHANGELOG.md` resume el proyecto en ocho hitos (H1 a H8)
y enumera los commits; el historial completo está en `git log`. Los resultados se versionan
(métricas, figuras, reportes); los datos y los artefactos regenerables, no.

## Notas técnicas

- `python-calamine` acelera la lectura de Excel unas 6 veces.
- **XGBoost con `count:poisson` necesita `base_score=1.0` explícito.** La estimación automática de
  XGBoost 2.x opera en la escala equivocada para este objetivo y el modelo devuelve una constante
  del orden de 1e13.
- `shap` 0.52 y `bottleneck` están compilados contra numpy 1.x. Con numpy 2 imprimen un aviso en
  stderr al importarse; no afecta el cálculo. Los cuadernos bloquean `bottleneck` para evitarlo.
