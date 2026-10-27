# Contexto para asistentes de IA

Capstone de maestría (UDLA, Grupo 5): predicción del volumen mensual de devoluciones de equipos móviles por marca.
Modelo: Poisson con offset de exposición (ventana W=9 meses, encogimiento k=300). Lee `README.md` para el pipeline.

## Antes de actuar, lee en este orden

1. `traspaso/INDICE.md` y la nota más reciente: qué se hizo, qué está pendiente y qué afirmaciones se corrigieron.
2. `README.md` (definición del target y pipeline) y `CHANGELOG.md`.
3. Verifica el estado: `git status`, `git log --oneline -6`, `python -m pytest tests` (49 pruebas).

## Reglas del usuario (obligatorias)

- **Sin commit ni push sin OK explícito.** Nunca `git add -A`: agrega solo los archivos propios.
- **Cero datos personales** en lo versionado: IMEI, RUC, PIDM, idBanner, correos, nombres de personas. Tampoco
  credenciales, tokens ni cadenas de conexión. No nombres locales o destinos concretos en notas ni documentos.
- **Los datos del cliente nunca se versionan** (`data/` está en `.gitignore`; también `Data*/`).
- Si el usuario pide «explícame» o «revisa», **no cambies archivos**.
- Atribución en commits: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Idioma: español.

## Lo que el repo NO contiene

- El informe final (`.docx`/`.pdf`) y el registro de correcciones: están fuera, en `DocumentosBdd`.
- Los datos crudos y el listado del negocio que valida la definición (99,75 %): solo en la máquina del autor.
- La clave de seudonimización definitiva: debe vivir fuera del repo y de OneDrive.

## Cuidado con estas cifras

- «99,75 %» es **cobertura** (799 de 801 del listado), no precisión: la definición marca 1.024 y 225 no están en el
  listado. Ver la nota de traspaso del 2026-10-26 (informe 010).
- El F1 máximo está en **75 días**; el 60 es una regla del negocio, no un óptimo.
- Solo **ago–sep 2026** es prueba intacta; ene–jul 2026 ya se usó en ciclos anteriores.
- El grano de OE3 es marca × mes.
