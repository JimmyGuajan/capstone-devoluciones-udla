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

## Estructura

```
├── Data tesis/ · Data/ · Data2/ · data 3/   entregas del cliente (no versionadas)
├── data/processed/             parquet generado — no versionar
├── src/
│   ├── config.py               rutas, umbral, marcas, ventana limpia
│   ├── parsers.py              limpieza de tipos y convenciones de fecha
│   ├── fuentes.py              lectores de despachos y snapshots
│   ├── sources.py              lectores de ventas y catálogos
│   ├── ciclo.py                primera definición del target (despachos + ventas)
│   ├── antiguedad.py           segunda definición (días en la misma bodega)
│   ├── permanencia.py          definición final, confirmada con el negocio
│   ├── extension.py            lector de la entrega complementaria (hoja TIGO)
│   ├── panel.py · events.py    utilidades de panel y eventos
│   ├── modelo.py               baselines, métricas, RF y XGBoost
│   └── warehouse.py            carga a SQL Server
├── notebooks/
│   ├── 01_limpieza_y_eda.ipynb              limpieza, estadías y paneles
│   ├── 02_modelo.ipynb                      primer modelo — trazabilidad
│   ├── 03_antiguedad_inventario.ipynb       validación contra los reportes del negocio
│   ├── 04_modelo_final.ipynb                modelo final
│   ├── 05_decision_modelo.ipynb             por qué se eligió ese modelo
│   ├── 06_extension_agosto_septiembre.ipynb entrega complementaria
│   ├── 07_validacion_estadistica.ipynb      walk-forward, bootstrap e incertidumbre
│   └── 08_interpretabilidad_y_equidad.ipynb SHAP y auditoría de trato por territorio
├── sql/                        consultas.sql · antiguedad.sql
├── docs/                       documento de entrega · solicitud de datos al cliente
├── reports/                    métricas en CSV, figuras y reportes HTML navegables
├── CHANGELOG.md                bitácora del proyecto
└── .claude/agents/             agente de revisión de entregables
```

## Ejecución

Requiere **Python 3.12**.

```bash
pip install -r requirements.txt
jupyter lab notebooks/01_limpieza_y_eda.ipynb   # ejecutar 01 antes que el resto
python -m src.warehouse                          # opcional: cargar a SQL Server
```

Orden de ejecución de los cuadernos:

| | Cuaderno | Qué hace |
|---|---|---|
| 1 | `01_limpieza_y_eda` | limpieza, estadías y paneles — **genera los parquet que leen los demás** |
| 2 | `02_modelo` | primer modelo; se conserva como trazabilidad |
| 3 | `03_antiguedad_inventario` | validación contra los listados del negocio |
| 4 | `04_modelo_final` | modelo final, Objetivos 3 y 4 |
| 5 | `05_decision_modelo` | por qué se eligió ese modelo |
| 6 | `06_extension_agosto_septiembre` | entrega complementaria, prueba de 9 meses |
| 7 | `07_validacion_estadistica` | walk-forward, bootstrap e incertidumbre |
| 8 | `08_interpretabilidad_y_equidad` | SHAP y auditoría de equidad por ciudad y distribuidor |

### Dependencias y versiones

| Paquete | Versión | Para qué |
|---|---|---|
| `pandas` | 2.2.3 | manipulación de datos |
| `numpy` | 2.0.2 | cálculo numérico |
| `scikit-learn` | ≥ 1.5 | Random Forest, `PoissonRegressor`, utilidades |
| `xgboost` | 2.1.3 | XGBoost con objetivo Poisson |
| `statsmodels` | ≥ 0.14 | GLM de Poisson de referencia |
| `shap` | ≥ 0.46 | explicabilidad |
| `pyarrow` | ≥ 15.0 | caché en parquet |
| `python-calamine` | ≥ 0.2 | lectura de Excel, 6× más rápida |
| `openpyxl` | 3.1.5 | respaldo de lectura de Excel |
| `matplotlib` | ≥ 3.8 | figuras |
| `duckdb` | — | consultas sobre parquet |
| `jupyterlab`, `nbformat` | — | cuadernos |

La primera corrida lee 1.075 snapshots y 35 archivos de despachos: unos 15 minutos. Después queda
todo cacheado en parquet.

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

- **Se excluye el 17 % de los periodos** (53.838 de 309.768) por no tener despacho asociado: son
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

## Notas técnicas

- `python-calamine` acelera la lectura de Excel unas 6 veces.
- **XGBoost con `count:poisson` necesita `base_score=1.0` explícito.** La estimación automática de
  XGBoost 2.x opera en la escala equivocada para este objetivo y el modelo devuelve una constante
  del orden de 1e13.
- `shap` 0.52 y `bottleneck` están compilados contra numpy 1.x. Con numpy 2 imprimen un aviso en
  stderr al importarse; no afecta el cálculo. Los cuadernos bloquean `bottleneck` para evitarlo.
