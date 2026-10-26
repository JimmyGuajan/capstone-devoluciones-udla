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
| **H8 · Interpretabilidad y equidad** | SHAP sobre los dos ensambles y auditoría de trato por ciudad y distribuidor | sesgo geográfico de −0,024 a +0,134 |
| **H9 · Entrega técnica del prototipo** | Scripts que reconstruyen toda la cadena y reproducen cada artefacto idéntico; modelo guardado; demo; 33 pruebas, con una de no-fuga; versiones fijadas; seudonimización | los 8 artefactos antes sin productor se reproducen exactos · sin cambio en las métricas |

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
| `17c34c0` | 2026-10-11 | Corregir cifras del documento y alinear el repositorio con lo que afirma |
| `9b4f95f` | 2026-10-11 | Acotar el documento a la predicción de devoluciones |
| `799b2e1` | 2026-10-11 | README: acotar el alcance a la predicción de devoluciones |
| `7214b40` | 2026-10-11 | README: corregir lo que decía de más y completar lo que faltaba |
| `e4d2b6b` | 2026-10-11 | Merge: ajustes al prototipo, validación estadística y consolidación |
| `6a76d67` | 2026-10-11 | Documento: quitar una redundancia en la síntesis reflexiva |
| `58e0dd9` | 2026-10-11 | Reporte de interpretabilidad y ética, con auditoría de equidad |
| `804cde4` | 2026-10-19 | Versionar los reportes HTML vigentes y retirar los superados |
| `af30818` | 2026-10-19 | Actualizar las cifras de volumen de «El camino hasta el modelo» |
| `9becf41` | 2026-10-26 | Seudonimización de identificadores, con prueba de equivalencia |
| `2d20910` | 2026-10-26 | Scripts que reconstruyen la cadena de datos y reproducen los artefactos |
| `ba8dc8c` | 2026-10-26 | Modelo final guardado, walk-forward con líneas base, demo y pruebas |
| `371e678` | 2026-10-26 | README con pipeline, pasos reales, demo y evidencias; versiones fijadas |
| `0dd2d45` | 2026-10-26 | Publicar la auditoría por destino con alias y retirar el PDF superado |
| `9ac9dcc` | 2026-10-26 | Aviso de derechos reservados con permiso de evaluación académica |
| `9de56ca` | 2026-10-26 | Merge: entrega técnica del prototipo |
