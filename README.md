# Predicción de devoluciones de inventario y ajuste de la demanda neta

Capstone — Maestría en Inteligencia Artificial Aplicada, Universidad de Las Américas.
Grupo 5: Guaján Perugachi Jimmy Israel · Martínez Ortega Jorge Washington · Vásquez Chávez Marco Vinicio.

Predice el volumen mensual de devoluciones de equipos móviles por marca, para ajustar la demanda
neta de un operador de telefonía con presencia en Ecuador.

## Definición del target

```
DEVOLUCIÓN := unidad despachada a un local que llega al día UMBRAL_DIAS
              sin haber salido de él (ni por venta ni por regreso a central)
GRANO      : marca × mes      VENTANA: 2025-01 a 2026-06 (18 meses)
```

Se construye cruzando el reporte de **despachos** (cuándo salió cada IMEI y a dónde) con los
**snapshots diarios de inventario** (dónde está cada IMEI cada día) y las **ventas serializadas**.

El umbral no se adopta por convención: se valida contra el retorno físico a bodega central, que sí
es observable en los snapshots (`barrido_umbral` en `src/ciclo.py`).

## Estructura

```
├── Data tesis/                 entrega del cliente, 2024-2026 (solo lectura)
├── data/processed/             parquet generado — no versionar
├── src/
│   ├── config.py               rutas, umbral, marcas, ventana limpia
│   ├── parsers.py              limpieza de tipos y convenciones de fecha
│   ├── fuentes.py              lectores de despachos y snapshots
│   ├── sources.py              lectores de ventas y catálogos
│   ├── ciclo.py                ciclo de vida por unidad y panel mensual
│   ├── modelo.py               baselines, métricas, RF y XGBoost
│   └── warehouse.py            carga a SQL Server
├── notebooks/
│   ├── 01_limpieza_y_eda.ipynb   fases 1-2 CRISP-ML(Q) · Objetivo 1
│   └── 02_modelo.ipynb           fases 3-4 CRISP-ML(Q) · Objetivos 3, 4 y 5
├── sql/consultas.sql
└── reports/                    métricas y figuras
```

## Ejecución

```bash
pip install -r requirements.txt
jupyter lab notebooks/01_limpieza_y_eda.ipynb   # ejecutar 01 antes que 02
python -m src.warehouse                          # opcional: cargar a SQL Server
```

La primera corrida lee 1.015 snapshots y 33 archivos de despachos: unos 15 minutos. Después queda
todo cacheado en parquet.

## Resultado

Sobre 4 meses de prueba (2026-03 a 2026-06), en el panel marca × mes:

| Modelo | WMAPE | MASE | MAPE mensual |
|---|---:|---:|---:|
| **XGBoost Poisson** | **0,403** | **0,276** | 28,0 % |
| Naive | 0,453 | 0,310 | 21,2 % |
| Media móvil 3m | 0,489 | 0,335 | 22,9 % |
| Random Forest | 0,764 | 0,523 | 76,1 % |
| Croston/SBA | 1,104 | 0,755 | 109,9 % |

XGBoost supera al naive en WMAPE y MASE. **No se alcanza el MAPE ≤ 15 % comprometido en el
Objetivo 4**, y la comparación por MAPE es inestable porque se mide sobre 4 puntos mensuales.

## Almacén SQL Server

`DW_DEVOLUCIONES_HIST` en `(localdb)\MSSQLLocalDB`: 27,9 M de filas en tres esquemas (`dim`,
`fact`, `mart`) con cinco vistas de negocio. Consultas de ejemplo en `sql/consultas.sql`.

## Decisiones de datos que hay que conocer

- **La ventana empieza en 2025-01.** El reporte de ventas de 2024 solo cubre cinco meses; sin
  ventas registradas las unidades vendidas parecen estancadas y el target se infla.
- **Se excluye el 8 % de unidades no rastreables** en los snapshots. El caso extremo eran 544
  unidades a un cliente institucional, todas con exactamente los mismos días, que producían un
  distribuidor con tasa de devolución del 100 %.
- **La madurez se mide contra el corte de ventas**, no el de inventario: el inventario llega al
  17 de septiembre y las ventas al 31 de agosto.
- **Se recortan los meses de cola** con menos del 30 % del volumen mediano de unidades maduras.
- **Las SIM quedan fuera**: su reporte de inventario trae el nombre de la bodega, no el código.

## Notas técnicas

- `python-calamine` acelera la lectura de Excel unas 6 veces.
- `shap` requiere `numpy<=2.0` por su dependencia de `numba`.
- **XGBoost con `count:poisson` necesita `base_score=1.0` explícito.** La estimación automática de
  XGBoost 2.x opera en la escala equivocada para este objetivo y el modelo devuelve una constante
  del orden de 1e13.
