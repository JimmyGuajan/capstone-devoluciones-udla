# Datos de muestra

Permiten probar el modelo, la demo y las pruebas **sin los datos del cliente**. Contienen solo totales
por marca y mes: ningún IMEI, ICCID, RUC, nombre de distribuidor ni de bodega.

| Archivo | Contenido |
|---|---|
| `panel_modelo_muestra.csv` | El panel marca × mes completo que usa el modelo: 319 filas, 29 meses (2024-05 a 2026-09), 11 marcas, 16 columnas. Es el mismo contenido que `data/processed/v6_panel_modelo.parquet`. |
| `en_riesgo_ejemplo.csv` | Ejemplo del formato de entrada para predecir un mes futuro: unidades en riesgo por marca. **Es ilustrativo**: copia las unidades en riesgo de septiembre de 2026, no las de octubre. |

Qué hay en cada columna del panel:

| Columna | Significado |
|---|---|
| `marca`, `mes` | grano del panel |
| `despachadas` | unidades despachadas ese mes |
| `devueltas` | unidades que cumplen 60 días en el mes: **el objetivo** que se predice |
| `en_riesgo` | unidades que cumplen 60 días en el mes y seguían en el canal al cierre del mes anterior (se conoce antes de que empiece el mes) |
| `valor` | valor de lo devuelto, al precio de despacho |
| `tasa` | `devueltas / despachadas` |
| `dev_lag1`–`dev_lag3`, `desp_lag1`–`desp_lag2` | devueltas y despachadas de uno a tres meses antes |
| `dev_mm3` | promedio de las devueltas de los tres meses anteriores |
| `r_marca` | tasa histórica de la marca: devueltas entre unidades en riesgo, acumuladas hasta el mes anterior |
| `mes_sin`, `mes_cos` | estacionalidad anual |

```bash
python scripts/predecir.py --mes 2026-09 --panel docs/muestra/panel_modelo_muestra.csv
python -m pytest tests          # las pruebas del modelo usan este panel
```
