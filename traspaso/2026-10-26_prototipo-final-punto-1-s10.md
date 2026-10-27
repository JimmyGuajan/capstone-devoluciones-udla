# Traspaso · Entrega técnica del prototipo (punto 1 de la tarea S10)

Fecha: 2026-10-26 · Rama de trabajo: `prototipo-final` (fusionada a `main` y subida; `main` en `9de56ca`) · Complementa a
[`2026-10-23_validacion-y-entregables-devoluciones.md`](2026-10-23_validacion-y-entregables-devoluciones.md),
cuyo pendiente sobre `equidad_destino.csv` y sobre la seudonimización quedó **superado** (ver §3).

## 1. Propósito

La tarea S10 «Avance consolidado del proyecto y documento final» pide, en su parte 1, la entrega técnica
del prototipo: código limpio y modular, modelo final entrenado y validado, documentación (README con
problema, requisitos, pasos e explicación del pipeline), control de versiones, demo y evidencias de
validación. El usuario aclaró que **lo «ejecutable» son solo pasos documentados** (el evaluador no
necesariamente ejecuta) y que la fecha de subida no importa. El orden acordado: primero el repositorio
(esta parte), después el documento final (informe de 76 páginas que el comité calificó 65/90).

## 2. Qué se hizo

Cuatro commits sobre `seudonimizacion`, más la licencia (`9ac9dcc`) y la fusión a `main` (`9de56ca`):

| Commit | Qué contiene |
|---|---|
| `2d20910` | `scripts/construir_v2.py`, `scripts/construir_v6.py`, `src/artefactos.py`; `src/panel_modelo.py` separa `periodos_desde_estadias` |
| `ba8dc8c` | `src/modelo_final.py`, `src/validacion.py`, `scripts/walk_forward.py`, `entrenar_y_evaluar.py`, `predecir.py`; `modelo/modelo_final.json`; `docs/muestra/`; `tests/test_modelo.py`; cuaderno 07 con líneas base; `reports/walkforward_con_lineas_base.csv` |
| `371e678` | README (pipeline, pasos, demo, pruebas, datos personales, evidencias), `requirements.txt` con versiones exactas, CHANGELOG (H9 y commits faltantes) |
| `0dd2d45` | `equidad_destino.csv` y cuaderno 08 con alias `DEST_01…`; PDF de septiembre fuera del seguimiento; `.gitignore` |

Resultado central: **los 8 artefactos que no tenían productor versionado se reproducen idénticos** desde
los scripts (`v2_estadias`, `v2_ciclo_unidad`, `v6_stock`, `v6_despachos`, `v6_estadias`, `v6_periodos`,
`v6_panel_modelo`, `v7_walkforward`). Las métricas del modelo **no cambiaron**.

## 3. Decisiones y hallazgos

- **Solo cuentan las ventas SELL_OUT** en `v2_ciclo_unidad`. `fact_ventas` mezcla SELL_IN (venta del
  fabricante al distribuidor, anterior a que la unidad llegue al local). Con todas las ventas, 21 de
  257.150 unidades salen «vendidas» sin serlo. La hipótesis previa («solo ventas posteriores al
  despacho») era falsa y se descartó midiendo.
- **Hiperparámetros del walk-forward ≠ los de la comparación en prueba.** Recuperados por búsqueda hasta
  diferencia 0: walk-forward RF 400/8/2 y XGBoost 400 árboles, profundidad 4, `min_child_weight=3`;
  comparación en prueba RF 600/8/2 y XGBoost 600. El documento final no debe mezclarlos.
- **Líneas base** (respuesta a NC-10): media móvil 3 meses 41,18 %, «cero» 100 %, naïve 34,96 %, modelo
  5,26 %. Van en tabla aparte; `v7_walkforward` conserva los 4 modelos originales.
- **Auditoría por destino con alias.** Cuaderno 08 y su CSV ya no publican nombres. Alias por orden de
  desviación (sin clave). **El historial de Git anterior aún contiene los nombres.**
- **Nombres de bodega siguen en claro** en cuadernos 01, 03 y 06, `src/antiguedad.py`, `src/permanencia.py`
  y `sql/antiguedad.sql` (la clasificación central/canal depende de ellos): fase 2 de la seudonimización.
- **PDF de septiembre** (`Documento_Capstone_..._003_2_02Sep2026_001.pdf`) fuera del repo y en
  `.gitignore`: su nombre de 88 caracteres rompía el clonado en rutas profundas de Windows.

## 4. Estado verificado

- 33 pruebas pasan (16 de seudonimización, 17 del modelo). La prueba de no-fuga por perturbación detecta
  tres fugas inyectadas.
- Clonando `prototipo-final` en una carpeta limpia (108 archivos, sin datos ni parquet) pasan las 33 pruebas
  y la demo funciona con el panel de muestra, con las mismas cifras.
- Cuaderno 07 (3 celdas nuevas) y 08 (alias): solo cambian las salidas esperadas; 0 errores ni avisos.
- **No verificado:** `pip install -r requirements.txt` en un entorno virtual nuevo (se usó el entorno
  existente). La seudonimización se verificó con clave de prueba, no con la definitiva.

## 5. Errores propios y correcciones

- Heredoc de Bash roto por comillas dentro del contenido: no modificó nada; se reescribió con la
  herramienta de archivos.
- Dos pruebas iniciales eran débiles (aserciones con `or True`): se sustituyeron por rezagos exactos y la
  prueba de perturbación, y se comprobó por mutación que detectan fugas.
- `python -m jupyter nbconvert` usó el Anaconda de la máquina y metió un `numexpr` compilado para NumPy 1.x:
  el README documenta `python -m nbconvert`.
- Primer clon de prueba falló por longitud de ruta (carpeta temporal profunda + PDF de nombre largo).
- El sistema bloqueó un `rm`/`rmdir` sobre `C:\Temp`: **quedó `C:\Temp\clon_pry` sin borrar** (clon de prueba).

## 6. Pendientes, por orden de importancia

1. ~~Push y fusión~~ **Hecho** (autorizado por el usuario): `prototipo-final` y `main` subidos.
2. ~~Licencia~~ **Hecho:** repo privado (verificado con `gh`), sin NDA adicional → `LICENSE` de «todos los derechos
   reservados, uso académico de evaluación». Si el repo se hiciera público habría que cambiar la licencia y limpiar el
   historial (conserva nombres de destinos).
3. **Seudonimización real:** generar la clave (`python -c "import secrets; print(secrets.token_hex(32))"`),
   guardarla fuera de OneDrive y del repo, ejecutar `scripts/seudonimizar_artefactos.py` y
   `scripts/verificar_equivalencia.py`; decidir si se borran los datos en claro; fase 2 (bodegas): el usuario decidió **no hacerla** y declararla como limitación en el documento.
4. **Documento final** (informe), corregido contra el repo: cifras (14,0 M filas, 775.024 estadías, 39.798
   eventos), descripción real del modelo (ventana 9 m, k=300), Anexo 4 con el mapeo real a 8 cuadernos y
   enlace al repo, cuadernos 07 y 08, tres ciclos de prueba y el holdout ago–sep 2026 intacto, OE3/OE4
   «cumplido parcialmente», Model Card, Python 3.12.4, USD 325 frente a 505, premisa del método vigente,
   y la seudonimización **solo en lo que realmente exista**.
5. Borrar `C:\Temp\clon_pry`; quedarse con `Interpretabilidad_y_etica_Grupo_5.pdf` (el otro PDF de ética del
   asistente está desactualizado); HTML de memoria y explorador desactualizados y sin versionar;
   `Libro1.xlsx` sin reproducir (correlación −0,74); almacén SQL sin recargar.

## 7. Reglas del usuario que siguen vigentes

- Sin `git add -A`: agregar solo los archivos propios. `traspaso/` no se commitea sin OK.
- Cero datos personales (IMEI, RUC, nombres de personas, correos) ni credenciales en lo versionado.
- Datos del cliente nunca versionados. La seudonimización no debe perjudicar los análisis.
- No hacer cambios cuando pide «explícame» o «revisa»; explicar antes de actuar si la decisión es suya.
- Atribución en commits: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## 8. Cómo retomar

Leer en este orden: este archivo → `README.md` (pipeline y pasos) → `CHANGELOG.md` → `docs/Interpretabilidad_y_etica_Grupo5.docx`.
Verificar el estado con `git status`, `git log --oneline -6` y `python -m pytest tests`.

## 9. Añadido después: sitio de defensa y hallazgos que afectan al documento final

- **Sitio de defensa** (`reports/html/defensa/`, generado por `scripts/generar_defensa.py`): cuatro páginas (problema,
  camino, solución, evidencia), modo claro y oscuro, cada cifra leída del código, de los reportes o de las salidas de los
  cuadernos. Pronóstico oct–dic (`src/proyeccion.py`): octubre 400 (283–517, error histórico a 1 mes 5,3 %);
  noviembre 617 y diciembre 664 son **escenarios** (error histórico 25,5 % y 40,0 %, no cumplen el 15 %).
- **Error del informe entregado (páginas 33 y 63):** afirma que 60 días maximizó el F1; el cuaderno 01 dice 75 (F1 0,137
  frente a 0,111 a 60 días). El 60 es la regla del negocio. Corregido en el reporte HTML y en el sitio; **pendiente en el
  informe**. Hay una prueba que impide reintroducirlo (`tests/test_defensa.py`).
- **«El conjunto de prueba no interviene en ninguna decisión» sobredeclara:** enero–julio de 2026 ya se había usado como
  prueba en ciclos anteriores. Lo realmente intacto es agosto–septiembre (entregado el 5 de octubre, con W y k fijados el 28
  de septiembre). Corregido en README, reporte HTML y sitio; **pendiente en el informe**.
- **«99,75 % de coincidencia» es cobertura, no precisión:** 799 de los 801 equipos del listado, pero el conjunto propio marca
  1.024, es decir 225 que el listado no trae. El repositorio no explica esos 225: **hay que averiguar el criterio del listado
  con el área de planificación** antes de que el comité lo pregunte. Además, el 95,4 % del cuaderno 03 es de otra definición y
  otro listado (367 equipos Samsung), no una medición previa de la definición final.
- El panel de vista previa del navegador abre pestañas por cada archivo escrito; se cerraron las sobrantes.
- Word por automatización: hay que evitar dejar procesos ocultos (ocurrió una vez; se cerró solo el propio).

