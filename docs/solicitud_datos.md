# Solicitud de datos complementarios

**Para:** Equipo de datos / Logística
**De:** Grupo 5 — Maestría en Inteligencia Artificial Aplicada, UDLA
**Asunto:** Solicitud de datos complementarios — proyecto de predicción de devoluciones

---

Estimados,

Agradecemos la entrega del histórico 2024-2026. Ya procesamos las cuatro fuentes y el modelo
predictivo está operativo: construimos la trazabilidad de cada equipo desde su despacho hasta su
venta o retorno, cruzando el reporte de despachos con los snapshots diarios de inventario.

Durante el procesamiento identificamos algunos vacíos. Detallamos abajo lo que necesitaríamos,
ordenado por impacto en la precisión del modelo.

---

## 1. Reporte de ventas de 2024 — siete meses faltantes

De la carpeta de ventas recibimos cinco archivos de 2024: **marzo, abril, agosto, septiembre y
diciembre**. Faltan:

- Enero 2024
- Febrero 2024
- Mayo 2024
- Junio 2024
- Julio 2024
- Octubre 2024
- Noviembre 2024

**Por qué importa.** Usamos el registro de venta para saber si un equipo se colocó o se quedó
detenido en el local. Cuando la venta no está registrada, el equipo aparece como estancado aunque
se haya vendido, y el modelo lo cuenta como devolución. Por esta razón tuvimos que descartar todo
2024 y trabajar únicamente desde enero de 2025.

Con estos siete archivos nuestra ventana de análisis pasaría de 18 a 33 meses. Es la solicitud de
mayor impacto: permitiría validar el comportamiento estacional con dos años completos en lugar de
uno.

## 2. Snapshots de inventario de noviembre 2025

La carpeta de noviembre de 2025 contiene solo **4 cortes** de los 30 días del mes: los días 11, 12,
26 y 27. ¿Sería posible regenerar los días faltantes?

*Observación menor, sin acción necesaria:* en esa misma carpeta hay 22 archivos nombrados
`01122025.xlsx` a `22122025.xlsx` que en realidad corresponden al 1–22 de diciembre y ya están
duplicados en la carpeta de diciembre. Lo mencionamos solo por si les sirve para ordenar el
repositorio.

## 3. Catálogo completo de bodegas (`Locations`)

El archivo recibido tiene 89 registros, pero en el reporte de despachos aparecen **965 destinos
distintos y 576 RUCs**. Nos falta identificar la mayor parte de la red, en particular el canal
zonificado.

Necesitaríamos el catálogo completo con estos campos:

- `Location Code`
- RUC del distribuidor
- Ciudad y provincia
- Canal
- Indicador de si la bodega es propia de Telefónica o de un distribuidor

## 4. `Masterfile` con todas sus columnas

El archivo recibido trae 6 columnas; la plantilla del reporte tiene 27. Nos faltan `GAMA`,
`TIPO_MATERIAL`, `PROVEEDOR`, `Product Family`, `Item Death` y los atributos técnicos.

Adicionalmente, los 251 registros corresponden solo a equipos y accesorios: **no está incluida la
familia de SIMs**.

## 5. Campo `Bodega ID` en el reporte de inventario de SIMs

El reporte de simcards trae el **nombre** de la bodega pero no su código, por lo que no podemos
cruzarlo con el catálogo de ubicaciones. Por esta razón las SIMs quedaron fuera del alcance del
modelo. Si el reporte puede incluir el campo `Bodega ID`, podríamos incorporarlas.

## 6. Un archivo vacío

El archivo `2.5.1.6+Ítems+de+inventario+IMEI+y+Número+Serial-02-24-2024+06-00.xlsx` llegó con
0 bytes. ¿Podrían reenviarlo?

---

## Tres consultas de negocio

Estas no requieren datos, solo su criterio. Es posible que correspondan al área de planificación de
demanda más que al equipo de datos.

**a)** ¿El umbral de 60 días para considerar un equipo como devolución esperada corresponde a una
política formal, o es una práctica operativa? Nuestro análisis sobre 18 meses sugiere que el punto
de mejor equilibrio está alrededor de los **75 días**, y quisiéramos saber si existe alguna
restricción documentada antes de proponer un ajuste.

**b)** ¿Podrían indicarnos qué bodegas son internas de Telefónica y cuáles corresponden a
distribuidores? Actualmente las identificamos por el nombre (`BODEGA CENTRAL`, `MATERIA PRIMA`,
`SCRAP`) y preferiríamos una lista formal para evitar clasificaciones erróneas.

**c)** Detectamos que cerca del **8 % de los equipos despachados nunca aparece en el inventario de
ningún local**. El caso más notorio son 544 unidades despachadas a `COMANDO CONJUNTO DE LAS FUERZAS
ARMADAS`. ¿Se trata de entregas directas que no pasan por bodega, o es un vacío del reporte de
inventario?

---

Si fuera necesario priorizar, los puntos **1, 2 y 3** son los que tienen mayor efecto sobre la
precisión del modelo.

Quedamos atentos y agradecemos su apoyo.

Saludos cordiales,

**Grupo 5**
Guaján Perugachi Jimmy Israel · Martínez Ortega Jorge Washington · Vásquez Chávez Marco Vinicio
Maestría en Inteligencia Artificial Aplicada — Universidad de Las Américas
