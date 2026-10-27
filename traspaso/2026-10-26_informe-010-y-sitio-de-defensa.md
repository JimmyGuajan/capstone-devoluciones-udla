# Traspaso — informe final 010, registro de correcciones y sitio de defensa

**Fecha:** 2026-10-26. **Contexto:** el informe 009 se calificó con 65/90 y 15 no conformidades (NC-01 a NC-15).
Esta sesión produjo el informe 010 y rediseñó el sitio de defensa. Lo de abajo es lo que no se deduce del código.

## 1. Qué se entregó (fuera del repo)

Están en `DocumentosBdd\Facturacion_Jimmy_Guajan\`, junto al 009. **No están versionados.**

| Archivo | Contenido |
|---|---|
| `Documento_Capstone_Grupo5_..._010_26Oct2026.docx/.pdf` | Informe final, 82 págs, mismo formato que el 009, todos los cambios resaltados en amarillo |
| `Registro_de_correcciones_Grupo5_010_26Oct2026.docx/.pdf` | Antes/después por NC, estado y acciones pendientes |
| `Guion_defensa_como_explicar_cada_seccion_Grupo5.docx/.pdf` | Cómo explicar cada sección del sitio de defensa |

Los generaba una carpeta temporal de la sesión (`ed.py`, `c1`–`c5.py`, `construir_010.py`, `build.py`, `registro.py`,
`guion.py`). **Esa carpeta no está en el repo ni se puede recuperar.** Si hay que rehacer el informe, se edita el `.docx`
010 directamente.

## 2. Qué cambió el 010 respecto del 009 (afirmaciones que sobredeclaraban)

- OE3 se declara a grano **marca × mes** (no distribuidor × SKU × mes: esa grilla tiene 7,6 % de densidad, 1,4 % de la grilla).
- OE4 y OE3 «cumplido parcialmente»; tres ciclos de prueba y solo **ago–sep 2026 intacto** (W y k fijados el 28-sep, datos recibidos el 5-oct).
- **El F1 máximo está en 75 días** (0,137 frente a 0,111 a 60), no en 60. El 60 es regla del negocio.
- El modelo real es Poisson con offset de exposición, ventana W=9 y encogimiento k=300; no «seis parámetros» ni `PoissonRegressor`.
- No hay panel Power BI; no hay cifrado/purga confirmados; la seudonimización existe en código pero **no se corrió con la clave definitiva**.
- Se quitaron «totalidad» e «íntegramente».

Cifras vigentes: MAPE de prueba 4,1 %, MAE 41,0, RMSE 69,9; walk-forward 21 orígenes 5,26 % [3,62–7,19];
14.007.314 filas de inventario → 775.024 estadías → 39.798 eventos → panel de 319 filas (11 marcas × 29 meses);
49 pruebas pasan.

## 3. Por qué «799 de 801» y no 801 (diagnosticado el 2026-10-26)

El listado de enero de 2025 (`Revision (1).xlsx`, solo en la máquina del autor, no versionado) trae 801 equipos; la
definición reproduce 799. Los 2 que faltan son equipos cuyo período en el canal **no tiene despacho asociado**, por lo
que `src/permanencia.py` los marca `sin_despacho` y los excluye de `validar`.

- **Equipo A:** pasó por un local, volvió a bodega central y salió de nuevo; la segunda salida no tiene registro de
  despacho. El único despacho queda a 21 días de la llegada. El listado cuenta 87 días desde el primer despacho y **no
  reinicia el reloj** tras la vuelta a central, lo que contradice la regla 2. Pregunta abierta para planificación.
- **Equipo B:** el despacho está fechado 14 días antes de la llegada al local; `con_despacho` acepta solo 10
  (`margen_dias=10`). Con un margen de 15 días lo capturaría.

No se cambió nada: mover el margen o la regla altera el panel y las cifras del informe.
**Son aparte de los 225 equipos** que nuestra definición marca (1.024) y el listado no trae: esos siguen sin explicar y
hay que preguntarle al área de planificación qué criterio usa el listado.

## 4. Sitio de defensa

`python scripts/generar_defensa.py` regenera `reports/html/defensa/{index,camino,solucion,evidencia}.html`
(autocontenidos, modo claro/oscuro) desde `scripts/defensa/`.

- Rediseño: banner granate UDLA con logo blanco (`scripts/defensa/udla_blanco.png`, incrustado en base64), etiqueta de
  página y botón «¿Cómo usar esta página?» con panel de ayuda por página. **Sin el texto «Inteligencia de la información».**
- Del banner de referencia solo se tomó el estilo y el logo; nada del contenido de «Docentes UDLA».
- Página 1: dice «Cobertura del listado del negocio: 799 de 801 (99,75 %)» y advierte que la definición marca equipos que el
  listado no trae. Es cobertura, no precisión.
- `tests/test_defensa.py` impide reintroducir la afirmación falsa del F1 en 60.
- `scripts/defensa/udla_color.png` existe pero no se usa. `reports/html/defensa.zip` es un empaquetado local, no versionado.

## 5. Scripts nuevos de esta sesión

| Script | Salida | Para qué |
|---|---|---|
| `scripts/sobredispersion_nb.py` | `reports/sobredispersion_nb.csv` | Binomial negativa NB2 (α=0,0129) frente a cuasi-Poisson (φ=8,86; cobertura 95,2 %) |
| `scripts/sensibilidad_hiperparametros.py` | `reports/sensibilidad_wk.csv` | Sensibilidad del error a W y k |
| `scripts/cifras_informe.py` | `reports/cifras_informe.csv` | Cifras reproducibles que cita el informe |

También: `src/seudonimizar.py` corrige el RUC de 12 dígitos con cero inicial, con su prueba nueva (49 pruebas).

## 6. Pendientes abiertos (`[CONFIRMAR]` en el 010)

1. Acta del Anexo 3: fecha, responsables y firmas.
2. Explicar los **225 equipos** que el listado no trae (§3).
3. Premisa del «método vigente»: proyección real y datos de obsolescencia.
4. Seudonimización con la clave definitiva (fuera de OneDrive y del repo) y confirmación de cifrado/purga.
5. Diferencia de 19 SKU (269 − 250).
6. Confirmar que las justificaciones de la sección 5.3 (planificado frente a ejecutado) son las reales.
7. Los pies de la Figura 1 y la Figura 7 del 010 dicen «redibujado/a»: es nota de cambio, no formato APA. Quitarla.
8. Invitar a los evaluadores al repositorio privado; decidir si se reescribe el historial (conserva nombres de destinos
   en `8262c6d` y `ef515d3`).

## 7. Reglas del usuario (siguen vigentes)

- Sin `git add -A`; agregar solo archivos propios. Sin commit ni push sin OK explícito.
- Cero datos personales (IMEI, RUC, PIDM, idBanner, correos, nombres de personas) ni credenciales en lo versionado.
  No nombrar locales/destinos concretos en notas.
- Datos del cliente nunca versionados (`data/` está en `.gitignore`).
- Si pide «explícame» o «revisa», no hacer cambios.

## 8. Cómo retomar

`CLAUDE.md` → este archivo → `README.md` → `CHANGELOG.md`. Verificar con `git status`, `git log --oneline -6` y
`python -m pytest tests`.
