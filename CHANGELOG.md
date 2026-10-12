# Bitácora del proyecto

Registro de cambios del prototipo de predicción de devoluciones de inventario.
Cada entrada corresponde a un commit del repositorio.

## Resumen por hitos

| Hito | Qué se hizo | Efecto medible |
|---|---|---|
| **H1 · Línea base** | Limpieza, construcción del target desde despachos e inventario, Random Forest y XGBoost | MAPE 28,3 % — no cumple el Objetivo 4 |
| **H2 · Diagnóstico** | Se contrasta la definición del target contra listados del área de planificación | 95,4 %, luego **99,75 %** de coincidencia |
| **H3 · Ingeniería de características** | Se construye `en_riesgo`, observable al cierre del mes anterior | correlación 0,982 con el objetivo |
| **H4 · Cambio de enfoque** | De ensambles a regresión de Poisson con offset de exposición | MAPE 28,3 % → **5,0 %** |
| **H5 · Hiperparámetros** | Ventana W = 9 meses y encogimiento k = 300, ajustados sobre validación | elimina el sesgo sistemático |
| **H6 · Extensión de datos** | Entrega complementaria de agosto y septiembre de 2026 | prueba de 7 a 9 meses · MAPE **4,1 %** |
| **H7 · Validación estadística** | Walk-forward de 21 orígenes, bootstrap y corrección de sobredispersión | IC 95 % [3,62 – 7,19] · cobertura 95,2 % |

## Historial de commits

| Commit | Fecha | Descripción |
|---|---|---|
| `a64d557` | 2026-09-19 | Pipeline de predicción de devoluciones de inventario |
| `8262c6d` | 2026-09-27 | Modelo final con la definición de devolución confirmada por el negocio |
| `822edc8` | 2026-09-28 | Tasa de conversión por marca y reporte del MAPE en el grano comprometido |
| `02c9f1d` | 2026-09-28 | Declarar el horizonte, la discrepancia abierta y la objeción previsible |
| `96c0fd0` | 2026-09-28 | Mostrar que RF y XGBoost cumplen el criterio, y declarar el grano |
| `f91bb0a` | 2026-09-28 | Nombrar el modelo por lo que es: Poisson con offset de exposición |
| `44654d0` | 2026-10-05 | Cuaderno 05: trazabilidad de la decisión de modelado |
| `ef515d3` | 2026-10-05 | Extensión a septiembre: prueba de 7 a 9 meses, MAPE 5,0 % -> 4,1 % |
| `daf022c` | 2026-10-11 | Validación estadística, bitácora y consolidación del repositorio |
| `d941697` | 2026-10-11 | Documento de entrega: ajustes, validación estadística y repositorio |
| `658f872` | 2026-10-11 | Documento: alcance en equipos móviles y cierre dirigido al revisor |
