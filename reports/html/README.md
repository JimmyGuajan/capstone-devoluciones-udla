# Reportes HTML

Páginas autocontenidas: se abren en cualquier navegador, sin servidor ni dependencias.

| Archivo | Qué muestra | Datos |
|---|---|---|
| `resultados_ene-sep_2026.html` | Resultado final: métricas, gráfico interactivo y tabla mes a mes. Julio, agosto y septiembre llevan un análisis del error al que se accede tocando el punto o la fila | prueba de **9 meses** |
| `el_camino_hasta_el_modelo.html` | Los once pasos del proyecto, del primer modelo al actual, con la evidencia de cada uno | prueba de **9 meses** |
| `demo_prediccion.html` | La demo: elegir uno de los nueve meses de prueba y ver predicción, intervalo del 95 %, valor real y detalle por marca; o ingresar unidades en riesgo para predecir un mes futuro | panel marca × mes y `modelo/modelo_final.json`; se regenera con `scripts/generar_demo_html.py` |

Las dos primeras se generaron a partir de los cuadernos 06 y 07. Las cifras coinciden con
`reports/metricas_v6.csv` y `reports/cuadro_v6.csv`.

Las versiones anteriores, con el conjunto de prueba de siete meses, se retiraron
al quedar superadas por la extensión a septiembre.
