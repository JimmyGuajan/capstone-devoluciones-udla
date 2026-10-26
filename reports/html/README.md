# Reportes HTML

Páginas autocontenidas: se abren en cualquier navegador, sin servidor ni dependencias.

| Archivo | Qué muestra | Datos |
|---|---|---|
| `resultados_ene-sep_2026.html` | Resultado final: métricas, gráfico interactivo y tabla mes a mes. Julio, agosto y septiembre llevan un análisis del error al que se accede tocando el punto o la fila | prueba de **9 meses** |
| `el_camino_hasta_el_modelo.html` | Los once pasos del proyecto, del primer modelo al actual, con la evidencia de cada uno | prueba de **9 meses** |
| `defensa/index.html` (+ `camino.html`, `solucion.html`, `evidencia.html`) | Sitio interactivo de cuatro páginas, con modo claro y oscuro, para la defensa: el problema (el viaje de un equipo, la regla de los 60 días), el camino (ocho paradas, de los datos al modelo, con la evidencia de cada decisión), la solución (flujo de datos, calculadora mes a mes, tasa por marca, pronóstico de octubre a diciembre) y la evidencia (resultados, walk-forward, intervalos, SHAP, equidad, límites) | panel marca × mes y reportes del repo; se regenera con `scripts/generar_defensa.py` |

Las dos primeras se generaron a partir de los cuadernos 06 y 07. Las cifras coinciden con
`reports/metricas_v6.csv` y `reports/cuadro_v6.csv`.

Las versiones anteriores, con el conjunto de prueba de siete meses, se retiraron
al quedar superadas por la extensión a septiembre.
