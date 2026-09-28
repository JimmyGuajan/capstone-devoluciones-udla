# Predicción de devoluciones de inventario y ajuste de la demanda neta

Capstone — Maestría en Inteligencia Artificial Aplicada, Universidad de Las Américas.
Grupo 5: Guaján Perugachi Jimmy Israel · Martínez Ortega Jorge Washington · Vásquez Chávez Marco Vinicio.

Predice el volumen mensual de devoluciones de equipos móviles por marca, para ajustar la demanda
neta de un operador de telefonía con presencia en Ecuador.

## Definición del target

```
DEVOLUCIÓN := unidad que cumple 60 días desde su fecha de despacho y sigue
              en poder del canal al cierre del mes
GRANO      : marca × mes      VENTANA: 2024-05 a 2026-07 (31 meses)
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
├── Data tesis/                 entrega del cliente, 2024-2026 (solo lectura, no versionado)
├── data/processed/             parquet generado — no versionar
├── src/
│   ├── config.py               rutas, umbral, marcas, ventana limpia
│   ├── parsers.py              limpieza de tipos y convenciones de fecha
│   ├── fuentes.py              lectores de despachos y snapshots
│   ├── sources.py              lectores de ventas y catálogos
│   ├── ciclo.py                primera definición del target (despachos + ventas)
│   ├── antiguedad.py           segunda definición (días en la misma bodega)
│   ├── permanencia.py          definición final, confirmada con el negocio
│   ├── modelo.py               baselines, métricas, RF y XGBoost
│   └── warehouse.py            carga a SQL Server
├── notebooks/
│   ├── 01_limpieza_y_eda.ipynb        fases 1-2 CRISP-ML(Q) · Objetivo 1
│   ├── 02_modelo.ipynb                primer modelo — se conserva como trazabilidad
│   ├── 03_antiguedad_inventario.ipynb validación contra los reportes del negocio
│   └── 04_modelo_final.ipynb          fases 3-4 CRISP-ML(Q) · Objetivos 3, 4 y 5
├── sql/consultas.sql, sql/antiguedad.sql
└── reports/                    métricas y figuras
```

## Ejecución

```bash
pip install -r requirements.txt
jupyter lab notebooks/01_limpieza_y_eda.ipynb   # ejecutar 01 antes que el resto
python -m src.warehouse                          # opcional: cargar a SQL Server
```

La primera corrida lee 1.015 snapshots y 33 archivos de despachos: unos 15 minutos. Después queda
todo cacheado en parquet.

## Resultado

Entrenamiento con 2024-2025, prueba sobre enero–julio de 2026 en el panel marca × mes. La
selección entre modelos se hace sobre un conjunto de validación intermedio (jul–dic 2025); el de
prueba no interviene en ninguna decisión.

| Modelo | WMAPE | MAE | RMSE | MASE | MAPE mensual |
|---|---:|---:|---:|---:|---:|
| **Regla de negocio** | **0,114** | **8,22** | 21,91 | **0,096** | **5,0 %** |
| Random Forest | 0,123 | 8,85 | **21,52** | 0,104 | 5,3 % |
| XGBoost Poisson | 0,157 | 11,31 | 25,18 | 0,133 | 10,3 % |

El Objetivo 4 fija el criterio sobre el **volumen mensual** (Plan v4: *"MAPE agregado ≤ 15 %"*).
A ese grano el resultado es:

| Grano | MAPE | MAE | RMSE | WMAPE |
|---|---:|---:|---:|---:|
| **Volumen mensual — criterio del OE 4** | **5,0 %** | 50,3 | 79,0 | 0,063 |
| Detalle marca × mes | 17,3 % | 8,2 | 21,9 | 0,114 |

Los tres modelos cumplen el criterio, de modo que el Objetivo 3 queda cubierto en sus propios
términos:

| Modelo | MAPE del volumen mensual | MAE | RMSE | ¿Cumple ≤ 15 %? |
|---|---:|---:|---:|:--|
| **Regla de negocio** | **5,0 %** | 50,3 | 79,0 | sí |
| Random Forest | 5,3 % | **48,4** | **66,5** | sí |
| XGBoost Poisson | 10,3 % | 77,1 | 89,5 | sí |

La elección se hizo sobre validación, donde la regla gana con holgura (6,0 % frente a 10,7 %).

**Se cumple el MAPE ≤ 15 % comprometido en el Objetivo 4.** A nivel de celda el MAPE es mayor
porque seis celdas de menos de 5 unidades —marcas que devuelven uno o dos equipos al mes— fallan
por 1,6 unidades en promedio y aportan casi un tercio de esa cifra; el MAPE se dispara cuando el
denominador tiende a cero. Por eso se reporta WMAPE en paralelo, que pondera por volumen.

El modelo ganador es el grupo en riesgo multiplicado por la **tasa de conversión de cada marca**,
reestimada cada mes con los 9 meses anteriores y encogida hacia la tasa global.
Las unidades que cumplirán 60 días el mes próximo ya son observables al cierre del mes actual
—fueron despachadas hace dos meses y se puede ver cuáles siguen en el canal—, y ese **grupo en
riesgo** correlaciona 0,982 con el resultado. SHAP le atribuye el 70,6 % de la contribución.

El aporte del trabajo no fue elegir el algoritmo, sino construir esa variable: la empresa no medía
el inventario detenido de forma sistemática.

### Qué cambió respecto de `02_modelo`

| | `02_modelo` | `04_modelo_final` |
|---|---:|---:|
| WMAPE (marca × mes) | 0,401 | **0,114** |
| MAE (marca × mes) | 18,59 | **8,22** |
| MAPE del volumen mensual | 28,3 % | **5,0 %** |
| Meses de historia | 18 | 31 |
| Validación contra el negocio | ninguna | 99,75 % |

Cuatro correcciones: la definición del target no era la del negocio; faltaba la variable
predictora principal; el histórico estaba recortado por una dependencia innecesaria del reporte de
ventas; y el modelo se elegía mirando el conjunto de prueba.

## Almacén SQL Server

`DW_DEVOLUCIONES_HIST` en `(localdb)\MSSQLLocalDB`: 27,9 M de filas en tres esquemas (`dim`,
`fact`, `mart`) con cinco vistas de negocio. Consultas de ejemplo en `sql/consultas.sql` y
`sql/antiguedad.sql`.

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
- **Agosto y septiembre de 2026 quedan fuera de la evaluación.** Una unidad despachada el 20 de
  julio cumple 60 días el 18 de septiembre, un día después del último inventario disponible;
  incluirlos produce una caída artificial al final de la serie.
- **Noviembre de 2025 tiene 4 días de inventario de 30.** Afecta el cálculo de antigüedad de las
  unidades que llegaron en ese período.
- **Las SIM quedan fuera**: su reporte de inventario trae el nombre de la bodega, no el código, y
  no se puede cruzar con el catálogo de ubicaciones.
- **HONOR concentra la mayor parte del error restante.** Su tasa de conversión oscila entre 0,28 y
  0,85 en siete meses. No es ruido del modelo: son acciones comerciales que movieron el inventario
  y que **ninguna variable disponible registra**. Es el principal argumento para pedir al cliente
  el histórico de promociones y cambios de precio por marca y mes.
- **La tasa de conversión es empírica y se reestima cada mes.** El modelo se adapta solo a cambios
  del canal, pero un cambio brusco tarda un par de meses en absorberse.

## Notas técnicas

- `python-calamine` acelera la lectura de Excel unas 6 veces.
- **XGBoost con `count:poisson` necesita `base_score=1.0` explícito.** La estimación automática de
  XGBoost 2.x opera en la escala equivocada para este objetivo y el modelo devuelve una constante
  del orden de 1e13.
- `shap` 0.52 y `bottleneck` están compilados contra numpy 1.x. Con numpy 2 imprimen un aviso en
  stderr al importarse; no afecta el cálculo. Los cuadernos bloquean `bottleneck` para evitarlo.
