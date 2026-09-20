---
title: "Plan de ejecución, gestión y modelado de datos"
subtitle: "Modelo de predicción de devoluciones de inventario y ajuste de la demanda neta de SIMs y equipos móviles"
author: "Grupo 5 — Maestría en Inteligencia Artificial Aplicada, Universidad de Las Américas"
date: "Versión 4.0 · 13 de septiembre de 2026"
lang: es
---

# 0. Propósito y alcance de este documento

Este documento traduce el proyecto capstone descrito en `Documento_Capstone_Grupo5_PredInvYAjusteDemandaNetaEmpTelefonica_003_2` en un plan operativo ejecutable: qué hacer, en qué orden, con qué datos, con qué herramientas y bajo qué criterios de aceptación.

Se apoya en dos marcos complementarios:

- **CRISP-ML(Q)** (Studer et al., 2021), metodología ya adoptada por el documento capstone y sobre la cual están construidos su cronograma y su estimación de costos.
- **"Fundamentos para Proyectos de IA"**, el mapa metodológico compartido por el equipo (XMind), cuyo contenido se incorporó a partir de la imagen entregada. La §12 presenta la trazabilidad nodo por nodo entre ese mapa y las secciones de este plan.

**Evolución del documento.**

- **v1.0** identificó tres bloqueos en ruta crítica: ausencia de pedidos, ausencia del target y profundidad de histórico desconocida.
- **v2.0** cerró los tres con las respuestas del cliente y la entrega de `ReporteLogistica.csv`, e incorporó el paso a paso del análisis exploratorio con recomendación de herramientas.
- **v3.0** cerró las confirmaciones de nomenclatura y clasificación, e incorporó dos restricciones que modifican el diseño del modelado: ventana de eventos de 12 meses y hasta tres cortes diarios.
- **v4.0 (esta versión)** incorpora los **catálogos de dominio** (`MO_TYPE`, `MO_STATUS`, `TYPE_`, `SO_TYPE`) y el resto de las respuestas operativas. Tres consecuencias de fondo: (a) la regla de clasificación deja de inferirse y pasa a apoyarse en `MO_TYPE`, que además revela **dos modelos comerciales distintos** —consignación y venta al partner— cuya devolución no es el mismo fenómeno (§1.4, N13); (b) `MO_STATUS` no contiene ningún valor "Tránsito", y la distinción entre `Submitted` y `Closed` introduce un **sesgo de censura en los períodos más recientes**, justo los que se usan para validación y prueba (N11); (c) los cortes diarios son **incrementales**, lo que reduce sustancialmente el riesgo de conteo múltiple (§5.5.1). La §5.8 revisa el tratamiento de datos personales a la luz de la respuesta a P10.

---

# 1. Estado del diagnóstico tras las respuestas del cliente

## 1.1 Bloqueos resueltos

| ID | Bloqueo v1 | Estado | Resolución |
|---|---|---|---|
| B1 | No existía fuente de **pedidos** | ✅ Resuelto | `ReporteLogistica.csv`: los pedidos son órdenes de movimiento cuya bodega destino pertenece a un distribuidor |
| B2 | No existía fuente explícita de **devoluciones** (el target) | ✅ Resuelto | Misma fuente: órdenes cuya bodega **origen** pertenece a un distribuidor y cuyo destino es la bodega central |
| B3 | Se desconocía la profundidad del **histórico** | ✅ Resuelto | Existen 24 meses de los tres reportes diarios, en formato y nomenclatura estables |
| **B7** | **Asimetría de ventana:** los snapshots cubren 24 meses, pero la fuente de eventos (`ReporteLogistica`) solo **12 meses** | 🟠 Mitigable | Confirmado en P23 que los snapshots de los 12 meses anteriores **están completos y sin días faltantes** → la extensión retrospectiva de §5.6.1 es viable |
| **B8** | Hasta 3 cortes diarios, con riesgo de conteo múltiple | ✅ **Muy reducido** | Confirmado en P20 que los cortes son **incrementales** (cada uno contiene información única). Se mantiene una verificación ligera entre días (§5.5.1) |
| **B9** | La entrega ocurre **por correo electrónico**, desde el **disco local de un equipo de logística**, sin política de retención | 🔴 **Elevado a alto** | Riesgo de continuidad y de cumplimiento. Ver N14 y §5.8 |
| **B10** | **`MO_STATUS` introduce censura a la derecha** en los períodos más recientes | 🔴 **Nuevo, alto** | Las órdenes aún en `Submitted` al momento del corte no se han consumado; los últimos períodos aparecerán sistemáticamente subestimados. Ver N11 y §7.7 |
| B4 | Volumetría de SIMs (1.460 M de registros) | 🟠 Vigente | Mitigado por la estrategia de agregación en ingesta (§5.3); se suma ahora el costo del *backfill* histórico (§5.4) |
| B5 | Series intermitentes con exceso de ceros | 🟠 Vigente | Se mantiene la estrategia de grano de producto y objetivo Tweedie/Poisson (§7) |
| B6 | Datos personales en claro (IMEI, ICCID, cuenta, teléfono) | 🟠 Vigente | Se mantiene el plan de seudonimización en ingesta (§5.8) |

## 1.2 Respuestas recibidas y su consecuencia técnica

| Pregunta | Respuesta del cliente | Consecuencia sobre el plan |
|---|---|---|
| **P2** Histórico | Existe. Mismo formato y nomenclatura estable para los tres reportes diarios | Se activa **Escenario A**. Se planifica *backfill* masivo (§5.4) |
| **P3** Pedidos | En `ReporteLogistica.csv`. Movimientos en estado "Tránsito"; pedido = bodega **destino** del distribuidor; devolución = bodega **origen** del distribuidor | `ReporteLogistica` pasa a ser la **tabla de hechos principal** del proyecto |
| **P4** Equivalencia de bodegas | La devolución se atribuye al distribuidor por la bodega del registro en los archivos 5 y 6 cuando el estado es "En Tránsito" y la bodega ≠ Bodega Central | Se obtiene además una **segunda fuente independiente** del target → habilita conciliación cruzada (§5.6) |
| **P5** Mapeo SKU de SIMs | "Se mapea a través del IMEI, código único de cada SIM" | ⚠️ Requiere precisión: ver hallazgo N4 |
| **P7** Histórico de cupos | No existe | El cupo entra como **atributo estático**; se solicita captura diaria desde hoy para uso futuro |
| **P8** Costo real | `Unit Cost` | Se descarta `Unit Cube` del modelo de datos |
| **P9** Enmascaramiento | Estable y determinístico | Los *joins* históricos sobre `Description` son seguros |
| **P11** Campañas | Día de la Madre (mes previo al 2.º domingo de mayo) y Navidad (mes previo al 24 de diciembre) | Se construye calendario de campañas explícito (§7.3) |
| **P12** Qué es una "baja" | Una baja es una venta al cliente final | El archivo 4 queda clasificado íntegramente como ***sell-out***; no contamina el target |
| **P13** Catálogos | Entregados los cuatro CSV de dominio | Ver §3.3. **Reordena la regla de clasificación** (§6.2) |
| **P15** Fecha de la devolución | Se contabiliza por **`CREATED_WHEN`** | Asignación temporal cerrada. Introduce el efecto de censura de N11 |
| **P17** Cantidad contable | **`APPROVED_QUANTITY`**; las demás son informativas | Target = suma de `APPROVED_QUANTITY`. El *fill rate* baja a variable exploratoria |
| **P18** Bodega central | Un solo código: **`PK`** | Regla de clasificación determinista. Verificar que `PK` aparezca en el dominio de `LOCATION_*_ID` |
| **P20** Cortes diarios | **Incrementales**: cada corte tiene información única; los 3 concatenados dan el total del día | Riesgo B8 muy reducido; se mantiene verificación entre días |
| **P21** Nombre del archivo | `ReporteLogistica` + `C` + nº corte + `F` + `MMDDAAAA` | El nº de corte está en el nombre → orden de los cortes resuelto. **Cuarta convención de fecha** (N15) |
| **P22** Canal y retención | Sin política de retención definida para el buzón | No es tranquilizador: sin política no hay garantía de permanencia. Ver N14 |
| **P23** Snapshots previos | Completos, sin días faltantes | **Habilita la extensión retrospectiva** (§5.6.1) |
| **P19** Ubicación del histórico | Disco local del equipo de logística, disponible de 06:00 a 23:59 | Copia masiva única en la primera semana; sin ventana nocturna de proceso |
| **P10** Datos personales | Canal = correo electrónico; **sin seudonimización en origen** | Requiere medidas compensatorias. Ver N14 y §5.8 |
| **P16** Llave evento ↔ unidad | Equipos: `IMEI` ↔ `EQUIPMENT_ID`. SIMs: `SERIE` ↔ `EQUIPMENT_ID` | Abre una vía limpia para el SKU (§5.5.2), pero la evidencia de la muestra la contradice. Ver N12 |

## 1.3 Hallazgos v2 — estado de resolución

| ID | Hallazgo v2 | Estado | Resolución confirmada |
|---|---|---|---|
| N1 | Nomenclatura del archivo 5 | ✅ Cerrado | El patrón real es **`Bodegas_AAAAMMDD`** (año-mes-día), como indicaba el archivo entregado |
| N2 | Nomenclatura del archivo 6 | ✅ Cerrado | El patrón real es **`MM-DD-AAAA`** (mes-día-año) |
| N3 | Formato del archivo 5 | ✅ Cerrado | Es **CSV** (texto delimitado). El entregado usa barra vertical como separador y extensión `.txt`: el lector debe aceptar ambas extensiones y no asumir coma |
| N4 | Identificador de las SIMs | ✅ Parcial | La SIM se identifica por el **IMSI**. Queda un punto abierto de segundo orden: ver N7 |
| N5 | Transferencias entre bodegas del mismo canal | ✅ Cerrado | **Se excluyen del alcance.** La regla de clasificación se simplifica a dos clases más un conjunto excluido (§6.2) |
| N6 | `MO_STATUS` de la muestra | ✅ Cerrado | El valor `Closed` de la muestra es ilustrativo, solo válido para identificar la cabecera. No condiciona la regla de negocio |

**Consecuencia sobre el parseo.** Las convenciones quedan fijadas así, y siguen siendo tres distintas conviviendo en el mismo proyecto:

| Fuente | Convención | Ejemplo |
|---|---|---|
| Archivo 4 — nombre | `DDMMAAAA` | `10092026.xlsx` = 10-sep-2026 |
| Archivo 4 — fechas internas | `MM-DD-AAAA HH-MM` | `09-10-2026 15-48` = 10-sep-2026 15:48 |
| Archivo 5 — nombre | `AAAAMMDD` | `Bodegas_20260912` = 12-sep-2026 |
| Archivo 6 — nombre | `MM-DD-AAAA` | `…Serial-09-11-2026_06-00` = 11-sep-2026 |
| `ReporteLogistica` — nombre | `MMDDAAAA` con nº de corte | `ReporteLogisticaC1F09122026.csv` = corte 1, 12-sep-2026 |
| `ReporteLogistica` — `CREATED_WHEN` | `DD/MM/AAAA HH:MM:SS` | `12/09/2026 12:54:28` = 12-sep-2026 |

El parser debe ser **explícito por archivo y por campo**. La inferencia automática de pandas sobre estas seis reglas produce errores silenciosos de hasta once meses. Conviene encapsularlas en un único módulo con pruebas unitarias: es el punto del *pipeline* con mayor densidad de trampas.

## 1.4 Hallazgos nuevos (v4)

**N11 · `MO_STATUS` no contiene "Tránsito", y la censura a la derecha sesgará los períodos recientes.** El catálogo tiene tres valores: `Submitted` (tareas vigentes que deben gestionarse), `Closed` (culminadas) y `Manually Closed` (cerradas en el sistema). Lo que el cliente llamó "Tránsito" corresponde a `Submitted`.

La consecuencia es sutil y seria. Si el target se contabiliza por `CREATED_WHEN` (P15), una devolución creada hace tres días aparece con estado `Submitted` y **puede no consumarse nunca**. Los períodos más recientes contendrán una proporción mayor de órdenes sin desenlace que los antiguos. Si se cuentan todas, el último mes queda inflado con intenciones; si se cuentan solo las `Closed`, queda deprimido porque a las recientes no les ha dado tiempo de cerrar. **En ambos casos el sesgo cae precisamente sobre los períodos de validación y prueba**, que son los más recientes, y contaminará la estimación del error.

Tratamiento propuesto:

1. Medir la **distribución del tiempo entre `CREATED_WHEN` y el cierre** (observable comparando cortes sucesivos: una línea pasa de `Submitted` a `Closed`). Sea *T* el percentil 95 de ese tiempo.
2. **Truncar la ventana del target** excluyendo los últimos *T* días: solo se modelan períodos con desenlace prácticamente completo.
3. Definir el target sobre `Closed` + `Manually Closed`, previa confirmación de que `Manually Closed` significa cumplida y no anulada (P24).
4. Registrar `%_submitted_al_corte` por período como variable de control y verificar que no correlacione con el error del modelo.

**N12 · La evidencia contradice el mapeo `SERIE` ↔ `EQUIPMENT_ID` para SIMs.** La respuesta a P16 indica que las SIMs se cruzan por `SERIE` (archivo 5) contra `EQUIPMENT_ID` (`ReporteLogistica`). Los datos de muestra apuntan en otra dirección:

| Campo | Longitud | Prefijo | Ejemplo |
|---|---|---|---|
| `EQUIPMENT_ID` (ReporteLogistica) | 19 | **917** | `9171088147113081563` |
| `IMSI` (archivo 5) | 19 | **917** | `9177173972113274888` |
| `Serie` / ICCID (archivo 5) | 19 | **895** | `8959300320591137292` |

`EQUIPMENT_ID` comparte el prefijo del **IMSI**, no el del ICCID —que empieza por 89, como manda el estándar—. A esto se suma que el mismo `EQUIPMENT_ID` aparece en dos líneas distintas y una de ellas tiene `APPROVED_QUANTITY = 2`, lo que es imposible para un identificador unitario.

**Prueba empírica que lo resuelve en una tarde** (no requiere respuesta del cliente): tomar un día de `ReporteLogistica` y el snapshot del mismo día, y calcular la tasa de coincidencia de `EQUIPMENT_ID` contra `Serie` y contra `IMSI`; en paralelo, tabular la distribución de `APPROVED_QUANTITY`.

- Si coincide con `Serie` o `IMSI` y las cantidades son casi siempre 1 → `EQUIPMENT_ID` es unitario y el mapeo del SKU queda resuelto por la vía de §5.5.2.
- Si no coincide o las cantidades son con frecuencia mayores que 1 → es un código de producto o de plantilla de eSIM con formato de IMSI, y el mapeo al SKU sigue abierto.

**N13 · Hay dos modelos comerciales distintos, y su devolución no es el mismo fenómeno.** El catálogo de `MO_TYPE` revela que los pedidos de distribuidores se registran bajo dos figuras: **`Consignación`** ("pedidos de distribuidores") y **`Venta al Partner`** ("pedidos de distribuidores cliente final"). Cruzado con `TYPE_`, que distingue `Sales` (con factura) de `Transfer` (sin factura), la diferencia es sustantiva:

- En **consignación** la mercadería sigue siendo propiedad de Telefónica en la bodega del distribuidor. Devolver es un movimiento logístico ordinario, de baja fricción y por tanto frecuente.
- En **venta al partner** la mercadería fue facturada. Devolver implica una reversión comercial, con nota de crédito y autorización. Es un evento más raro, más costoso y gobernado por otros incentivos.

Mezclar ambos en un mismo target modela dos procesos distintos como si fueran uno. **Recomendación:** incorporar `MO_TYPE` como dimensión de segmentación desde el EDA (paso E7), comparar la tasa de devolución y el perfil de intermitencia de cada figura y, si difieren de forma marcada, entrenar **modelos separados** o incluir la figura como variable de primer orden. Es probable que este sea el hallazgo con mayor valor de negocio del proyecto, porque sugiere que la palanca de gestión no es la misma en ambos casos.

Nótese además que `Abastecimiento a tiendas propias` ("pedidos de puntos propios") **no corresponde a distribuidores**: queda fuera del target definido en el alcance, aunque conviene conservarlo como contexto y contraste.

**N14 · La cadena de suministro de datos es el punto más frágil del proyecto.** Combinando P19, P22 y P10: los archivos residen en el **disco local del computador de logística**, disponible de 06:00 a 23:59; se comparten por **correo electrónico**; **no existe política de retención** del buzón; y los datos **no se seudonimizan en origen**, de modo que ICCID, IMEI, cuenta de cliente y número telefónico circulan por correo.

Dos implicaciones separadas:

- **Continuidad.** Todo el histórico de 24 meses depende de que una máquina esté encendida y de un buzón sin garantías de permanencia. **Acción inmediata: realizar la copia masiva completa del histórico en la primera semana**, a un almacenamiento controlado por el equipo, y no volver a depender de ese disco para datos históricos. Postergarlo es asumir un riesgo evitable.
- **Cumplimiento.** El correo electrónico no es un canal adecuado para datos personales bajo la LOPDP, y el documento capstone ya asume compromisos explícitos en materia de protección de datos. Medidas compensatorias en §5.8. Conviene además dejar constancia de esta observación en las recomendaciones del informe: es exactamente el tipo de hallazgo que un trabajo de titulación puede aportar a la organización, y refuerza la sección de ética que ya contempla el documento.

**N9 y N10 (vigentes de v3).** La ventana de eventos sigue siendo de 12 meses, de modo que el grano mensual deja 12 observaciones por serie (§7.2.1), cada campaña comercial se observa una sola vez y el rezago `y[t-12]` no existe salvo que prospere la extensión retrospectiva de §5.6.1 —que la confirmación de P23 ahora hace viable.

**N15 · Cuarta convención de fecha.** El patrón `ReporteLogisticaC{n}F{MM}{DD}{AAAA}` añade `MMDDAAAA` sin separadores al repertorio. El proyecto maneja ahora cuatro convenciones en nombres de archivo y dos en campos internos (§1.3). El número de corte viaja en el nombre, lo que resuelve el ordenamiento de los cortes sin necesidad de un campo de marca temporal.

---

# 2. Preguntas abiertas para la próxima reunión

| # | Pregunta | Criticidad |
|---|---|---|
| **P24** | **¿`Manually Closed` significa orden cumplida o anulada?** | 🔴 Determina si esas líneas entran o no en el target (N11) |
| **P25** | ¿`EQUIPMENT_ID` identifica una unidad o un producto? Confirmar tras la prueba empírica de N12, aportando los resultados | 🔴 Condiciona la vía del SKU (§5.5.3) |
| **P26** | ¿Por qué una línea con `APPROVED_QUANTITY = 2` comparte `EQUIPMENT_ID` con otra? | 🟠 Aclara N12 |
| **P27** | ¿La bodega central `PK` figura en `Locations.xlsx`? ¿Conviven códigos cortos y largos en `LOCATION_*_ID`? | 🟠 Valida la regla de §6.2 |
| **P28** | ¿Se puede enviar los adjuntos cifrados y/o seudonimizados en origen? (ver §5.8.1) | 🟠 Cumplimiento LOPDP |
| **P29** | ¿Existe respaldo del histórico fuera del equipo de logística? | 🟠 Continuidad (N14) |
| P6 | Proceso de negocio de la devolución: política, plazos máximos, autorizaciones, si genera nota de crédito. **Distinguir consignación de venta al partner** (N13) | 🟠 Define el horizonte útil de predicción |

Las preguntas P10, P13, P15 a P23 quedaron respondidas y se registran en §1.2.

---

# 3. Inventario de datos consolidado

## 3.1 Modelo de datos objetivo

```
                         ┌────────────────────────────┐
                         │  dim_distribuidor          │
                         │  Cupo_Disponible...xlsx    │
                         │  PK: Custom Attribute Code │
                         │      (= RUC, 13 dígitos)   │
                         │  ⚠ snapshot único, sin     │
                         │    histórico (P7)          │
                         └─────────────┬──────────────┘
                                       │ RUC
                         ┌─────────────┴──────────────┐
                         │  dim_bodega                │
                         │  Locations.xlsx (96)       │
                         │  PK: Location Code         │
                         │  → región, provincia,      │
                         │    ciudad, canal,          │
                         │    categorización, BU      │
                         └─────────────┬──────────────┘
                                       │ Location Code
    ┌──────────────────┬───────────────┼───────────────┬──────────────────┐
    │                  │               │               │                  │
┌───┴──────────────┐ ┌─┴───────────┐ ┌─┴───────────┐ ┌─┴──────────────┐
│ fact_ordenes     │ │ fact_sellout│ │ fact_stock_ │ │ fact_stock_sim │
│ ★ ReporteLog.csv │ │ 10092026... │ │ equipo      │ │ Bodegas_*.txt  │
│ EVENTOS          │ │ EVENTOS     │ │ 2.5.1.6...  │ │ SNAPSHOT       │
│ grano: línea de  │ │ grano: unid.│ │ SNAPSHOT    │ │ ~2.000.000/día │
│ orden + cantidad │ │ 1k–50k/día  │ │ ~11.000/día │ │ grano: Serie   │
│ → PEDIDOS        │ │ → ventas a  │ │ grano: IMEI │ │   (ICCID)      │
│ → DEVOLUCIONES   │ │   cliente   │ │             │ │                │
│ → transferencias │ │   final     │ │             │ │                │
└───┬──────────────┘ └─┬───────────┘ └─┬───────────┘ └─┬──────────────┘
    │ EQUIPMENT_NAME   │ Artículo      │ Cód. artículo │ Modelo (⚠ N4)
    └──────────────────┴───────────────┼───────────────┴─────────────────┘
                         ┌─────────────┴──────────────┐
                         │  dim_sku                   │
                         │  Masterfile.xlsx           │
                         │  PK: Código del artículo   │
                         │  Unit Cost (real, P8)      │
                         └────────────────────────────┘
```

★ = fuente primaria de la variable objetivo.

## 3.2 Ficha del archivo nuevo: `ReporteLogistica.csv`

Formato: delimitado por `;`, saltos CRLF, 26 columnas, fechas `DD/MM/AAAA HH:MM:SS`.
**Ventana disponible: 12 meses** (frente a 24 de los snapshots). **Frecuencia: hasta 3 cortes por día.** **Canal de entrega: correo electrónico.**

| Grupo | Campos |
|---|---|
| Identificación | `WORK_ITEM_ID`, `MOVEMENT_ORDER_ID`, `MOVE_ORDER_LINE_ID`, `CONTEXTID` |
| Clasificación | `TYPE_` (*Transfer*), `MO_TYPE` (*Movimiento entre bodegas de TFN*), `MO_STATUS` (*Closed*), `SO_TYPE` |
| Temporalidad | `CREATED_WHEN` |
| Cliente | `CUSTOMER_ID`, `CUSTOMER_NAME` (vacíos en la muestra) |
| Producto | `EQUIPMENT_NAME`, `EQUIPMENT_ID`, `ARTICLE`, `EQUIPMENT_CONDITION`, `PREACTIVATION_TEMPLATE_ID/NAME` |
| **Origen y destino** | `LOCATION_FROM_NAME`, **`LOCATION_FROM_ID`**, `LOCATION_TO_NAME`, **`LOCATION_TO_ID`** |
| **Cantidades** | `APPROVED_QUANTITY`, `RESERVED_QUANTITY`, `DISPATCHED_QUANTITY`, `RECEIVED_QUANTITY`, `TO_BE_DISPATCHED` |

**Por qué este archivo reordena el proyecto:**

1. `LOCATION_FROM_ID` y `LOCATION_TO_ID` usan **el mismo formato `Location Code`** que `Locations.xlsx` (`CELINDAMBCEL5660`, `CELINDQUIAGE0241`). El *join* bodega → distribuidor es directo y limpio, sin tabla de equivalencia. Esto era el bloqueo P4.
2. Está a **nivel de línea con cantidad**, no de unidad individual. Es órdenes de magnitud más ligero que los snapshots y directamente agregable al panel de modelado.
3. Contiene simultáneamente pedidos y devoluciones, lo que permite calcular la **demanda neta** sobre una sola fuente coherente, sin problemas de conciliación entre sistemas.
4. Las cantidades aprobada / despachada / recibida permiten derivar un ***fill rate*** y detectar cumplimiento parcial — una señal de comportamiento del distribuidor que no existía en ninguna otra fuente.

## 3.3 Catálogos de dominio (respuesta P13)

**`MO_TYPE` — figura comercial del movimiento**

| Valor | Descripción del cliente | Tratamiento en el proyecto |
|---|---|---|
| `Consignación` | Pedidos de distribuidores | ✅ **En alcance.** Mercadería en consignación: la propiedad no se transfiere |
| `Venta al Partner` | Pedidos de distribuidores cliente final | ✅ **En alcance.** Mercadería facturada al partner |
| `Abastecimiento a tiendas propias` | Pedidos de puntos propios | ⚪ Fuera del target (no son distribuidores); conservar como contexto y contraste |
| `Movimiento entre bodegas de TFN` | Tareas no vinculadas a pedidos | ⚠️ **No excluir en bloque.** Ver la advertencia de §6.2 |

**`TYPE_` — naturaleza del documento**

| Valor | Descripción | Uso |
|---|---|---|
| `Sales` | Ventas al partner | Implica factura; se espera que acompañe a `Venta al Partner` |
| `Transfer` | Transferencias sin factura | Se espera que acompañe a `Consignación` y a los movimientos entre bodegas |

Tabular el cruce `MO_TYPE` × `TYPE_` en el EDA: las combinaciones inesperadas (por ejemplo `Consignación` con `Sales`) señalan casos de negocio que conviene entender antes de modelar.

**`MO_STATUS` — estado de la tarea**

| Valor | Descripción | Implicación |
|---|---|---|
| `Submitted` | Tareas vigentes que deben ser gestionadas | Orden **sin desenlace**. Es lo que el cliente llamaba "Tránsito". Fuente de la censura de N11 |
| `Closed` | Tareas culminadas en el sistema | Desenlace confirmado |
| `Manually Closed` | Tareas cerradas en el sistema | **Ambiguo:** ¿cumplida o anulada? Ver P24 |

**`SO_TYPE`**

| Valor | Descripción |
|---|---|
| `Distribution Request` | Tareas que aplican a distribuidores retail |

Valor único en el catálogo: sin poder discriminante, se conserva solo como validación de que no aparecen valores fuera de dominio.

## 3.4 Recordatorio de hallazgos de calidad ya detectados (vigentes)


- **Masterfile:** `?` como token de nulo en ~85 % de los atributos técnicos; fechas centinela `Item Birth Year` = 1990 e `Item Death Year` = 2075; `Unit Cube` a descartar (P8).
- **Archivo 4:** campos con coacción de texto de Excel (`=""`, `="11778731"`); `Id Bodega Origen/Destino` con convención propia (`VU`, `106`) que **no** coincide con `Location Code` — relevante solo si se usa este archivo para geolocalizar el *sell-out*.
- **Archivo 5:** literal `"NULL"` en texto, no nulo real; `CodigoComercial` es identificador por unidad, **no** el SKU; `Bodega` es nombre, no código; el campo `Lote` (`MES01557`) habilita el cálculo de antigüedad del stock de SIMs.
- **Archivo 6:** las 3 primeras filas son encabezado de reporte (`skiprows=3`); `Bodega ID` **sí** usa `Location Code`; `Condición del equipo` (Nuevo/Usado/**Obsoleto**) permite medir directamente el KPI de obsolescencia del proyecto (5,9 % actual vs. 2,9 % meta).
- **Locations:** una fila con `Location Code` vacío; sentinelas `OTRAS`/`OTROS`; jerarquía geográfica redundante (`County` = región, `Zona Courier` = provincia, `City` = ciudad).

---

# 4. Definición formal del problema de ML

Artefacto de cierre de la Fase 1 de CRISP-ML(Q). Debe firmarse antes de escribir código de modelado.

```
TAREA      : Regresión supervisada sobre conteos no negativos con exceso de ceros

TARGET     : y[d, g, t+h] = unidades devueltas por el distribuidor d,
             del grupo de producto g, durante el período t+h

  DEVOLUCIÓN := línea de orden en ReporteLogistica tal que
                  LOCATION_FROM_ID ∈ bodegas de distribuidor
                  Y LOCATION_TO_ID = "PK"          (P18: código único central)
                  Y MO_STATUS ∈ {Closed, Manually Closed}   (pendiente P24)
                cantidad := APPROVED_QUANTITY       (P17: cifra contable)
                fecha    := CREATED_WHEN            (P15)
                segmento := MO_TYPE ∈ {Consignación, Venta al Partner}
                            → dos figuras comerciales distintas (N13)

  VENTANA      : truncada en los últimos T días, con T = p95 del tiempo
                 entre CREATED_WHEN y el cierre, para evitar la censura
                 a la derecha de N11

  FUENTE PRIMARIA   : fact_ordenes (ReporteLogistica.csv), DEDUPLICADO por
                      línea de orden a través de los 3 cortes diarios (§5.5)
                      Ventana: 12 meses
  FUENTE DE CONTROL : snapshots 5 y 6, registros con estado "En Tránsito"
                      y bodega ≠ Bodega Central  →  conciliación cruzada (§5.6)
                      Ventana: 24 meses  →  habilita extensión retrospectiva

  EXCLUIDO DEL TARGET:
    · transferencias entre bodegas del mismo canal o distribuidor (N5,
      decisión confirmada por el cliente)
    · ventas a cliente final y "bajas" (archivo 4) — ambas son sell-out (P12)

GRANO      : distribuidor (RUC) × grupo_producto × período
             período = semana o mes según §7.2 (la ventana de 12 meses
             condiciona esta decisión)
HORIZONTE  : h = 1 período; evaluar h = 2 según lead time de abastecimiento

FEATURES   : exclusivamente información disponible al cierre de t.
             Ningún campo cuyo valor se conozca después de t.

USO        : DemandaNetaAjustada[d,s,t+1] = Pedido[d,s,t+1] − α · ŷ[d,s,t+1]
             (α = factor de confianza por celda, §9.1)

RIESGO     : subestimar la devolución es más costoso que sobreestimarla
ASIMÉTRICO   (genera sobre-stock → obsolescencia). Se penaliza en la
             función objetivo y se reporta como métrica específica.
```

**Corrección al documento capstone:** la celda *Sep S3* del cronograma menciona "Random Forest y XGBoost (clasificación y regresión)", lo que contradice la §4.2 del alcance, que excluye explícitamente la clasificación. Debe eliminarse la mención a clasificación.

---

# 5. Plan de gestión de datos

## 5.1 Arquitectura de capas

Arquitectura medallón simplificada, ejecutable en equipo local, sin nube — coherente con la Propuesta A seleccionada en el documento.

```
/data
 ├── 00_landing/            ← archivos del cliente, INMUTABLE, solo lectura
 │     └── AAAA-MM-DD/
 ├── 01_bronze/             ← parquet tipado, sin transformación semántica
 │     ├── ordenes/fecha=AAAA-MM-DD/
 │     ├── sellout/fecha=AAAA-MM-DD/
 │     ├── stock_equipo/fecha=AAAA-MM-DD/
 │     ├── stock_sim_agg/fecha=AAAA-MM-DD/
 │     └── _sim_state/      ← índice de estado por Serie (retención 2 días)
 ├── 02_silver/             ← llaves resueltas, PII seudonimizada, eventos clasificados
 │     ├── dim_sku.parquet · dim_bodega.parquet · dim_distribuidor.parquet
 │     ├── dim_calendario.parquet      ← incluye campañas (§7.3)
 │     ├── fact_eventos.parquet        ← pedidos, devoluciones, transferencias
 │     └── fact_stock_diario.parquet
 └── 03_gold/
       ├── panel.parquet               ← un registro por (distribuidor, grupo, mes)
       └── splits/{train,valid,test}.parquet
```

**Regla dura:** `00_landing` nunca se modifica ni se sobrescribe. Todo lo demás debe ser reconstruible ejecutando el *pipeline* desde cero. Es lo que permite versionar con DVC sin duplicar cientos de gigabytes y lo que hace verificable la reproducibilidad exigida por el nodo 7 del mapa metodológico.

## 5.2 Contrato de datos

Un YAML por archivo fuente en `contracts/`, con: patrón de nombre, frecuencia, codificación, delimitador, columnas con tipo esperado, obligatorias no nulas, dominios cerrados, llave primaria y tokens de nulo. Ejemplo abreviado:

```yaml
nombre_logico: stock_sim
patron_archivo: "Bodegas_{AAAA}{MM}{DD}.(txt|csv)"   # ✅ confirmado v3
frecuencia: diaria
encoding: utf-8
delimitador: "|"
tokens_nulos: ["NULL", ""]
llave_primaria: [IMSI]
columnas:
  IMSI:         {tipo: str, nulo: false}        # llave unitaria — se hashea en bronze
  Serie:        {tipo: str, nulo: false}        # ICCID — se hashea en bronze
  Modelo:       {tipo: str, nulo: false}        # SKU de SIM
  Bodega:       {tipo: str, nulo: false}        # nombre, requiere mapeo
  EstadoLogico: {tipo: cat, dominio: [Planned, Disponible, EnTransito, Reservado, EnUso]}
  Condicion:    {tipo: cat, dominio: [Normal, Usado, Obsoleto]}
  Costo:        {tipo: float, min: 0}
  Lote:         {tipo: str, nulo: true}
validaciones_lote:
  filas_esperadas: {min: 1500000, max: 2500000}
```

Este archivo alimenta directamente las validaciones automáticas y es un anexo evaluable del capstone.

## 5.3 Ingesta diaria y volumetría

**`ReporteLogistica.csv` y archivo 4:** volumen moderado. Lectura directa a parquet, tipado explícito, sin agregación.

**Archivo 6 (equipos, 11 k/día):** a nivel de IMEI sin agregar. 24 meses ≈ 8 M registros ≈ 200 MB en parquet. Directo.

**Archivo 5 (SIMs, 2 M/día):** requiere agregar en ingesta y persistir los deltas por separado.

```python
import polars as pl

LAYOUT = {"IMSI": pl.Utf8, "Serie": pl.Utf8, "Modelo": pl.Utf8,
          "CodigoComercial": pl.Utf8, "EstadoLogico": pl.Categorical,
          "Condicion": pl.Categorical, "PropiedadActual": pl.Categorical,
          "MIN": pl.Utf8, "Bodega": pl.Utf8, "Preactivacion": pl.Categorical,
          "CodVario1": pl.Utf8, "CodVario2": pl.Utf8, "Costo": pl.Float64,
          "CodVario3": pl.Utf8, "Lote": pl.Utf8}

lf = pl.scan_csv(ruta, separator="|", schema=LAYOUT, null_values=["NULL", ""])

# (a) Agregado para modelado y tableros: ~5.000 filas/día
(lf.group_by(["Bodega", "Modelo", "EstadoLogico", "Condicion", "Lote"])
   .agg(unidades=pl.len(), costo_total=pl.col("Costo").sum())
   .with_columns(fecha=pl.lit(fecha))
   .sink_parquet(f"01_bronze/stock_sim_agg/fecha={fecha}/part.parquet"))

# (b) Índice de estado para el diff del día siguiente
(lf.select(["IMSI", "Bodega", "EstadoLogico", "Condicion"])   # IMSI = llave unitaria
   .sink_parquet(f"01_bronze/_sim_state/{fecha}.parquet"))
```

Con esto, el almacenamiento de 24 meses de SIMs pasa de aproximadamente **220 GB de texto plano a menos de 2 GB**, y el dataset de modelado cabe cómodamente en memoria.

## 5.4 Plan de *backfill* del histórico (24 meses)

Es la actividad más pesada del proyecto: aproximadamente **730 archivos × 3 reportes diarios ≈ 2.190 archivos**, más unos **1.095 archivos de `ReporteLogistica`** (365 días × hasta 3 cortes). Cerca de **3.300 archivos en total**.

**Patrones de descubrimiento — confirmados en v3:**

```python
PATRONES = {
    # nombre DDMMAAAA, fechas internas MM-DD-AAAA
    "sellout":      r"^(?P<d>\d{2})(?P<m>\d{2})(?P<a>\d{4})\.xlsx$",
    # ✅ confirmado: AAAAMMDD; CSV delimitado por '|', extensión .txt o .csv
    "stock_sim":    r"^Bodegas_(?P<a>\d{4})(?P<m>\d{2})(?P<d>\d{2})\.(txt|csv)$",
    # ✅ confirmado: MM-DD-AAAA
    "stock_equipo": r"^2\.5\.1\.6.*Serial-(?P<m>\d{2})-(?P<d>\d{2})-(?P<a>\d{4})[_ ]06-00\.xlsx$",
    # ✅ confirmado: MMDDAAAA con nº de corte en el nombre
    "ordenes":      r"^ReporteLogisticaC(?P<corte>\d+)F(?P<m>\d{2})(?P<d>\d{2})(?P<a>\d{4})\.csv$",
}
```

**Estimación de esfuerzo de procesamiento** (a validar con un lote piloto de 7 días):

| Reporte | Archivos | Filas/archivo | Ventana | Costo dominante |
|---|---|---|---|---|
| `stock_sim` | ~730 | 2.000.000 | 24 meses | Parseo de texto — el más costoso; paralelizar por proceso |
| `stock_equipo` | ~730 | 11.000 | 24 meses | Apertura de xlsx; usar `read_only=True` en openpyxl |
| `sellout` | ~730 | 1.000–50.000 | 24 meses | Apertura de xlsx |
| `ordenes` | **~1.095** | variable | **12 meses** | Parseo CSV bajo; cortes incrementales, concatenación directa (§5.5.1) |

**Copia masiva del histórico — acción de primera semana.** Confirmado en P19 que los 24 meses residen en el **disco local del computador de logística**, accesible solo de 06:00 a 23:59, y en P22 que **no existe política de retención** del buzón. Toda la base empírica del proyecto depende hoy de que una máquina permanezca encendida. **La copia íntegra del histórico a un almacenamiento controlado por el equipo debe ejecutarse en la primera semana**, antes que cualquier otra tarea de datos, y verificarse con conteo de archivos y hash por archivo. Postergarla es asumir un riesgo evitable con costo de recuperación total.

La ventana de disponibilidad de 06:00 a 23:59 además descarta la ejecución nocturna: toda extracción programada debe caer dentro de ese horario.

**Recepción por correo electrónico.** La entrega por buzón introduce modos de falla que un canal de sistema no tiene: adjuntos truncados por límite de tamaño, correos duplicados o reenviados, asuntos inconsistentes, y un buzón sin garantías de permanencia. Procedimiento mínimo:

1. **Extracción automatizada** con `imaplib` (IMAP) o Microsoft Graph, filtrando por remitente y asunto, hacia `00_landing/AAAA-MM-DD/`.
2. **Manifiesto de recepción** por archivo: `message-id`, fecha del correo, nombre del adjunto, tamaño en bytes y hash SHA-256. La deduplicación de correos reenviados se hace por hash del adjunto, no por nombre —el mismo corte reenviado dos veces tiene el mismo contenido y distinto `message-id`.
3. **Verificación de integridad** antes de ingerir: tamaño distinto de cero, número de columnas correcto, y conteo de filas dentro del rango esperado. Un adjunto truncado por límite de tamaño se detecta aquí y no meses después, cuando el modelo ya se entrenó sobre él.
4. **Registro de cobertura:** días con menos de los cortes esperados, o días sin ningún correo.
5. **Recomendación formal al cliente (P22):** migrar a SFTP o carpeta compartida. El correo es aceptable para un piloto de titulación, pero no es un canal sostenible para la fase de producción descrita en la Propuesta B, y conviene dejarlo escrito en las recomendaciones del capstone.

**Recomendaciones operativas del *backfill*:**

1. **Convertir una sola vez a parquet.** Nunca releer los xlsx originales durante la iteración de modelado: leer xlsx con openpyxl es entre uno y dos órdenes de magnitud más lento que leer parquet.
2. **Paralelizar por archivo** con `multiprocessing.Pool` o `joblib` (cada día es independiente). Con 8 procesos el tiempo total se reduce de forma aproximadamente lineal.
3. **Ejecutar en dos olas:** primero los 3 meses más recientes (permite arrancar el EDA y el modelado baseline de inmediato), luego los 21 restantes en segundo plano. Esto desbloquea el cronograma sin esperar al *backfill* completo.
4. **Checkpointing:** registrar en un manifiesto qué archivos fueron procesados con éxito, cuántas filas produjeron y su hash. Un *backfill* de 2.190 archivos fallará en alguno; debe poder reanudarse, no reiniciarse.
5. **Registro de cobertura:** identificar días faltantes en la secuencia. Un snapshot ausente rompe el *diff* del día siguiente (§5.6) y debe marcarse.

## 5.5 Deduplicación de cortes y resolución de llaves

### 5.5.1 Consolidación de los tres cortes diarios

**Confirmado en P20: los cortes son incrementales.** Cada corte contiene información única y los tres concatenados dan el total de pedidos del día. Esto reduce drásticamente el riesgo B8: la operación por defecto es **concatenar, no deduplicar**.

El número de corte viaja en el nombre del archivo (`ReporteLogisticaC{n}F{MMDDAAAA}`), de modo que el orden queda determinado sin necesidad de un campo de marca temporal:

```python
PAT = re.compile(r"ReporteLogisticaC(?P<corte>\d+)F(?P<m>\d{2})(?P<d>\d{2})(?P<a>\d{4})", re.I)

def leer_dia(archivos):
    partes = []
    for f in sorted(archivos, key=lambda x: int(PAT.search(x)["corte"])):
        g = PAT.search(f)
        partes.append(leer(f).with_columns(
            fecha_archivo=pl.date(int(g["a"]), int(g["m"]), int(g["d"])),
            n_corte=pl.lit(int(g["corte"]))))
    return pl.concat(partes)
```

**Dos verificaciones que conviene mantener igualmente**, porque el costo es bajo y el costo de equivocarse es alto:

1. **Solapamiento intra-día.** Contar líneas duplicadas por `MOVE_ORDER_LINE_ID` entre los tres cortes del mismo día. Debe ser ≈ 0. Si no lo es, la premisa de incrementalidad no se cumple para todos los días y hay que volver a P20.
2. **Reaparición entre días.** Una línea creada hoy en estado `Submitted` podría volver a listarse mañana ya como `Closed`, dado que `Submitted` designa "tareas vigentes que deben ser gestionadas". Medir cuántas líneas aparecen en más de un día: si ocurre, la regla correcta es conservar **el último registro por `MOVE_ORDER_LINE_ID`**, que refleja el desenlace. Esta medición es además el insumo directo para estimar el tiempo hasta el cierre que exige el tratamiento de la censura (N11).

**Control de aceptación:** el total mensual del target debe cuadrar con la fuente B (§5.6) dentro del 5 %. Un desvío cercano a un múltiplo entero (2× o 3×) delata un problema de consolidación, no de interpretación del negocio.

### 5.5.2 Resolución de llaves — estado actualizado

| *Join* | Llave izquierda | Llave derecha | Estado |
|---|---|---|---|
| Orden → Bodega origen/destino | `LOCATION_FROM_ID` / `LOCATION_TO_ID` | `Location Code` | ✅ **Resuelto** por `ReporteLogistica` |
| Equipo → SKU | `Código del artículo` (arch. 6) | `Código del artículo` | ✅ Limpio |
| Equipo → Bodega | `Bodega ID` (arch. 6) | `Location Code` | ✅ Limpio |
| Bodega → Distribuidor | `Distribuidor para Cupo (Atrib 10)` | `Custom Attribute Code` | 🟡 Normalizar RUC como texto de 13 dígitos |
| Orden → SKU | `EQUIPMENT_ID` → snapshot | `Código del artículo` | 🟡 **Vía del snapshot** (§5.5.3), condicionada a N12 |
| *Sell-out* → SKU | `Artículo` (arch. 4) | `Código del artículo` | 🟡 Confirmar mismo dominio |
| *Sell-out* → Bodega | `Id Bodega Origen/Destino` | `Location Code` | 🟠 Convención propia; necesario solo si se geolocaliza el *sell-out* |
| SIM → identidad de unidad | `IMSI` | — | ✅ Llave unitaria interna para el *diff* de snapshots |
| SIM → SKU | vía `EQUIPMENT_ID` → snapshot | `Código del artículo` | 🟡 **Vía abierta, pendiente de N12** |
| SIM → Bodega | `Bodega` (nombre) | `Location Code` | 🟠 Mapeo por nombre; validar con *fuzzy matching* y revisión manual |

### 5.5.3 El snapshot como puente entre el evento y el SKU

La respuesta a P16 abre una vía elegante que conviene explicitar, porque no era evidente: `ReporteLogistica` no necesita contener el SKU. Si `EQUIPMENT_ID` identifica la unidad —el `IMEI` para equipos, el `Serie`/`IMSI` para SIMs—, entonces el SKU se obtiene **atravesando el snapshot**, que sí lo lleva:

```
ReporteLogistica.EQUIPMENT_ID
        │
        ├─ equipos → archivo 6 .IMEI ──→ .Código del artículo ──→ Masterfile
        │
        └─ SIMs    → archivo 5 .Serie / .IMSI ──→ .Modelo ──────→ Masterfile (P16)
```

Ventajas de esta vía: no depende de que `ARTICLE` esté poblado (viene vacío en la muestra), y los snapshots son diarios a lo largo de 24 meses, así que la unidad casi siempre estará presente en alguno.

Detalles de implementación:

- Construir una **tabla de referencia unidad → SKU** consolidada sobre todo el histórico, no un *join* contra el snapshot de un día. Una unidad puede no aparecer en el snapshot del día exacto del movimiento (si salió del universo), pero sí en días cercanos.
- El archivo 5 contiene `IMSI` y `Serie` en la misma fila, de modo que la correspondencia entre ambos es gratuita: se resuelve el cruce sin importar cuál de los dos use `EQUIPMENT_ID`.
- Medir la **tasa de cobertura**: porcentaje de líneas de `ReporteLogistica` que logran resolver su SKU. Umbral de aceptación: > 95 %. Por debajo, investigar antes de modelar.
- **Todo esto está condicionado a N12.** Si la prueba empírica revela que `EQUIPMENT_ID` es un código de producto y no de unidad, esta vía se cae y hay que volver a P16 con la evidencia en la mano.

## 5.6 Doble fuente del target y conciliación cruzada

El cliente entregó, sin proponérselo, **dos caminos independientes hacia la misma variable objetivo**. Aprovecharlo es el principal control de calidad del proyecto y un aporte metodológico defendible ante el tribunal.

| | Fuente A — eventos | Fuente B — estado |
|---|---|---|
| Origen | `ReporteLogistica.csv` | Archivos 5 y 6, registros `En Tránsito` con bodega ≠ Bodega Central |
| Naturaleza | Orden de movimiento con cantidad | Unidades individuales observadas en tránsito |
| Ventaja | Explícita, con origen, destino y cantidad | Independiente del sistema de órdenes |
| Limitación | Depende de que la orden se registre | Solo captura el estado neto diario |

### 5.6.1 Extensión retrospectiva del target — la oportunidad clave de esta versión

La asimetría de ventanas (12 meses de eventos frente a 24 de snapshots, hallazgo N9) es un problema, pero la doble fuente ofrece una salida: **si la fuente B reproduce fielmente a la fuente A durante los 12 meses en que ambas existen, entonces B es confiable para reconstruir el target en los 12 meses en que A no existe.**

```
mes -24 ─────────────────── mes -12 ─────────────────── hoy
│                            │                            │
│  Snapshots (fuente B)      │  Snapshots (fuente B)       │
│  ✅ disponibles            │  ✅ disponibles             │
│                            │                            │
│  ReporteLogistica (A)      │  ReporteLogistica (A)       │
│  ❌ NO disponible          │  ✅ disponible              │
│                            │                            │
│  ← target RECONSTRUIDO     │  ← ventana de CALIBRACIÓN   │
│    (si pasa la validación) │    y VALIDACIÓN de B        │
```

**Confirmado en P23** que los snapshots de los 12 meses anteriores están completos y sin días faltantes, lo que elimina la principal incertidumbre de esta vía: el *diff* día a día puede ejecutarse sin interrupciones en toda la ventana.

**Protocolo:**

1. Calcular el target por ambas vías en los 12 meses de solapamiento.
2. Medir la concordancia por (distribuidor, mes): correlación, sesgo medio y WMAPE de B respecto de A.
3. **Criterio de aceptación:** si el WMAPE de B contra A es menor al 10 % y el sesgo no es sistemático por distribuidor ni por zona, se acepta B como *proxy* del target para los 12 meses anteriores.
4. Si se acepta, el panel de entrenamiento pasa de 12 a **24 períodos mensuales**, se recuperan **dos observaciones de cada campaña** en lugar de una, y el rezago `y[t-12]` vuelve a ser utilizable.
5. **Marcar el origen del target** con una variable `target_origen ∈ {observado, reconstruido}` y verificar que el modelo no aprenda a distinguirlos. Reportar las métricas por separado para ambos subconjuntos: si el desempeño difiere mucho, la reconstrucción está introduciendo ruido.
6. Si el criterio no se cumple, descartar la extensión y aplicar el replanteo de grano de §7.2. **No forzar la reconstrucción**: un target ruidoso es peor que un target corto.

Este procedimiento —calibrar una fuente derivada contra una fuente directa en su ventana de solapamiento y usarla para extender la historia— es defendible metodológicamente y constituye un aporte del trabajo, siempre que se documente el criterio de aceptación **antes** de mirar el resultado.

### 5.6.2 Conciliación continua

**Procedimiento:** para cada (distribuidor, mes), comparar el total de devoluciones de A contra el conteo derivado de B.

- Desvío < 5 % → se usa A como fuente oficial y B como control continuo.
- Desvío 5–20 % → investigar la causa (órdenes no registradas, tránsitos de más de un día contados doble, transferencias mal clasificadas) y documentar.
- Desvío > 20 % → hay un error de interpretación de la regla de negocio; volver a P13/P15 antes de modelar.

**Advertencia sobre la fuente B:** una unidad que permanece "En Tránsito" durante varios días aparece en varios snapshots consecutivos. Contar filas por día produciría sobreconteo. Hay que contar **entradas al estado** (transiciones), no presencias — lo que se resuelve con el *diff* de snapshots:

```python
prev = pl.read_parquet(f"01_bronze/_sim_state/{t_menos_1}.parquet")
curr = pl.read_parquet(f"01_bronze/_sim_state/{t}.parquet")

transiciones = (
    prev.join(curr, on="Serie", how="full", suffix="_c")
        .filter((pl.col("EstadoLogico") != pl.col("EstadoLogico_c")) |
                (pl.col("Bodega")       != pl.col("Bodega_c")))
        .with_columns(fecha=pl.lit(t))
)
# Devolución en curso := transición a "EnTransito" desde bodega de distribuidor
```

## 5.7 Validación automática de calidad

Implementar con `pandera` (ligero, integrado con pandas y polars) o Great Expectations. Se ejecuta en cada ingesta; el fallo detiene el *pipeline*.

1. **Esquema:** columnas presentes con el tipo declarado en el contrato.
2. **Unicidad:** `IMSI` único por snapshot de SIMs; `IMEI` único por snapshot de equipos; `MOVE_ORDER_LINE_ID` único en órdenes.
3. **Dominio cerrado:** `EstadoLogico`, `Condicion`, `MO_TYPE`, `MO_STATUS` contra catálogo. Un valor nuevo genera alerta, no se ignora.
4. **Volumetría:** conteo de filas dentro de ±3σ de la media móvil de 30 días. Un archivo de SIMs con 400.000 filas es una extracción truncada, no una caída de inventario.
5. **Continuidad temporal:** no faltan fechas en la secuencia diaria.
6. **Integridad referencial:** porcentaje de filas cuya bodega o SKU no existe en la dimensión. Umbral de alerta: > 1 %.
7. **Coherencia de cantidades:** `RECEIVED_QUANTITY ≤ DISPATCHED_QUANTITY ≤ APPROVED_QUANTITY`. Las violaciones son señal de dato o de proceso.
8. **Rangos:** costos ≥ 0; fechas dentro de la ventana histórica declarada.
9. **PII:** ninguna columna con patrón de IMEI (15 dígitos), ICCID (19–20 dígitos) o teléfono debe sobrevivir sin hashear más allá de bronze.

Cada ejecución genera un **reporte de calidad fechado y versionado** — el artefacto "data validation" comprometido en el cronograma (Ago S4) y anexo directo del capstone.

## 5.8 Privacidad y cumplimiento LOPDP

| Campo | Tratamiento | Justificación |
|---|---|---|
| `IMSI`, `Serie`/ICCID, `IMEI` | HMAC-SHA256 con sal secreta fuera del repositorio | Se requiere identidad **estable** para el *diff* entre días, no el valor real |
| `Cuenta de Cliente`, `Login`, `Número Telefónico Asociado`, `MIN`, `CUSTOMER_ID/NAME` | **Eliminar en bronze** | Minimización de datos; no aportan poder predictivo al target agregado |
| `Número de Factura` | Eliminar; conservar flag `tiene_factura` | Sin valor predictivo |
| Distribuidor (RUC, razón social) | Seudónimo estable `DIST_0001…`, tabla de mapeo fuera del repositorio | Permite la auditoría de equidad sin exponer identidad comercial |
| Geografía (región, provincia, ciudad) | Conservar | Necesaria para la auditoría de sesgo comprometida en el alcance |

La sal criptográfica y la tabla de seudónimos viven en `.env` o gestor de secretos, **nunca en Git**. Añadir un *hook* de `pre-commit` que bloquee cualquier commit con patrones de IMEI, ICCID o RUC.

### 5.8.1 Medidas compensatorias por el canal de entrega (respuesta P10)

El cliente confirma que el canal es el correo electrónico y que **los datos no se seudonimizan en origen**. El correo no cifrado no es un canal adecuado para datos personales bajo la LOPDP, y el documento capstone ya asume compromisos explícitos en esta materia. Dado que el canal no está bajo control del equipo, corresponden medidas compensatorias y una recomendación formal:

1. **Seudonimizar en el primer punto bajo control del equipo.** El *hashing* de ICCID, IMEI, IMSI y cuenta de cliente ocurre en la transición de `00_landing` a `01_bronze`, antes de cualquier análisis. Ningún identificador en claro sale de `landing`.
2. **Cifrar `00_landing` en reposo** (contenedor cifrado o cifrado de disco) y restringir su acceso a los integrantes del equipo.
3. **Purgar el buzón tras la ingesta:** eliminar los correos una vez verificado el manifiesto. Al no existir política de retención (P22), la ausencia de política significa ausencia de garantías, no permanencia indefinida.
4. **Solicitar formalmente al cliente** (a) el envío de adjuntos cifrados con contraseña transmitida por un canal distinto, y (b) la seudonimización en origen de los campos que el proyecto no necesita en claro. La respuesta, sea cual sea, debe quedar documentada.
5. **Registrar la observación en el informe.** Que el canal de distribución de datos personales sea el correo sin cifrar es un hallazgo legítimo del proyecto y pertenece a las recomendaciones, no solo al plan interno. Es el tipo de aporte que un trabajo de titulación puede devolver a la organización.

**Minimización, que es la medida más eficaz:** el target se construye a nivel agregado (distribuidor × grupo × período). Los identificadores unitarios solo se necesitan para el *diff* de snapshots y para resolver el SKU vía §5.5.3, ambas operaciones que funcionan igual de bien sobre valores hasheados. **El proyecto no necesita un solo IMEI, ICCID o IMSI en claro más allá de `landing`.**

## 5.9 Versionado y reproducibilidad

- **Git** para código; **DVC** para datos y modelos.
- Semilla fija global (`numpy`, `random`, `sklearn`, `xgboost`); `requirements.txt` con versiones ancladas.
- **MLflow** para *tracking*: cada corrida registra parámetros, métricas, hash del dataset de entrada y artefacto del modelo.
- **Makefile** con objetivos `make backfill`, `make ingest`, `make eda`, `make features`, `make train`, `make evaluate`, `make report`. Es el *pipeline* reproducible del cronograma sin el peso de una orquestación que nadie mantendrá después de la defensa.

---

# 6. Paso a paso del proyecto (Fases CRISP-ML(Q))

## 6.1 Cronograma replanteado — Escenario A confirmado

| Semana | Fase | Actividades | Entregable / criterio de aceptación |
|---|---|---|---|
| **Sep S2** (actual) | 1 | Enviar P13–P19; inicializar repositorio; escribir contratos de datos | Acta enviada; repo con estructura §11; 7 contratos YAML |
| **Sep S3** | 1→2 | *Backfill* ola 1 (3 meses); lectores y parsers; **deduplicación de cortes validada**; extracción desde buzón | Bronze operativo sobre 3 meses; validaciones en verde 3 días seguidos; naturaleza de los cortes determinada |
| **Sep S4** | 2 | Clasificación de eventos; conciliación A vs B; **decisión sobre extensión retrospectiva (§5.6.1)**; **EDA completo (§8)** | `fact_eventos` validado y deduplicado; vía de grano temporal decidida; informe de EDA con ≥2 variables asociadas a devolución → **cierra Objetivo Específico 1** |
| **Oct S1** | 2→3 | *Backfill* ola 2 (21 meses); panel gold; *feature engineering*; baselines | `panel.parquet` particionado; baselines naive, media móvil y Croston/SBA evaluados |
| **Oct S2** | 3 | Random Forest y XGBoost; tuning con `TimeSeriesSplit`; SHAP | Modelo candidato registrado en MLflow; MASE < 1 en validación |
| **Oct S3** | 4 | Evaluación en *holdout* temporal; auditoría de equidad | Reporte de evaluación; MAPE agregado ≤ 15 %; equidad aprobada |
| **Oct S4** | 5→6 | Piloto; tablero Power BI; monitoreo; informe final | Piloto operativo; *model card*; plan de reentrenamiento |

**Punto de control:** viernes 19 de septiembre. Si el *backfill* ola 1 no está operativo, adelantar la ola 2 y recortar el alcance del piloto.

## 6.2 Regla de clasificación de eventos (núcleo del proyecto)

```python
CENTRAL = {"PK"}                                  # P18: código único de bodega central
DISTRIB = set(dim_bodega.filter(
    pl.col("Distribuidor para Cupo").is_not_null())["Location Code"])

MO_DISTRIBUIDOR = {"Consignación", "Venta al Partner"}
MO_PROPIAS      = {"Abastecimiento a tiendas propias"}

def clasificar(r):
    o, d, mo = r["LOCATION_FROM_ID"], r["LOCATION_TO_ID"], r["MO_TYPE"]
    o_cd, d_cd   = o in CENTRAL, d in CENTRAL
    o_di, d_di   = o in DISTRIB, d in DISTRIB

    if o_cd and d_di and mo in MO_DISTRIBUIDOR: return "PEDIDO"      # sell-in
    if o_di and d_cd:                           return "DEVOLUCION"  # ★ TARGET
    if o_cd and d_di and mo in MO_PROPIAS:      return "TIENDA_PROPIA"  # contexto
    if o_di and d_di:                           return "EXCLUIDO"    # N5
    return "OTRO"                                                    # revisar
```

**Advertencia sobre el uso del catálogo.** Sería tentador excluir en bloque `MO_TYPE = "Movimiento entre bodegas de TFN"` por estar descrito como "tareas no vinculadas a pedidos". **Sería un error.** La exclusión acordada en N5 es la de los movimientos cuyo **origen y destino son ambos bodegas de distribuidor**, no la de una etiqueta. Una devolución hacia `PK` puede perfectamente registrarse bajo esa figura, precisamente porque no está vinculada a un pedido. Por eso la regla se mantiene **gobernada por la dirección** (origen y destino), con `MO_TYPE` como atributo secundario y como variable del modelo.

La verificación correspondiente en el EDA es tabular la distribución de `MO_TYPE` **dentro** de las líneas ya clasificadas como `DEVOLUCION`. Si resulta que la mayoría son `Movimiento entre bodegas de TFN`, la advertencia anterior queda confirmada empíricamente.

**Validaciones asociadas a la regla:**

- Confirmar que `PK` aparece efectivamente en el dominio de `LOCATION_FROM_ID` y `LOCATION_TO_ID`. Las filas de muestra usan códigos largos (`CELINDQUIAGE0241`), de modo que `PK` convive con otro formato: comprobarlo antes de dar la regla por buena.
- Verificar que `PK` existe también en `Locations.xlsx`; si no está, añadirlo manualmente a `dim_bodega`.
- Tabular `MO_TYPE` × `TYPE_` × clase asignada. Las combinaciones inesperadas se revisan con el cliente.

Los casos `OTRO` deben tabularse y revisarse; su volumen indica la calidad del catálogo de bodegas. Umbral de aceptación: < 2 % de las líneas.

Adicionalmente, el **ratio de transferencias excluidas sobre pedidos** sigue siendo valioso como **variable predictora** aunque no forme parte del target: un distribuidor que redistribuye mucho entre sus bodegas está corrigiendo una asignación inicial equivocada, lo que anticipa devolución.

---

# 7. Plan de modelado

## 7.1 Construcción del panel

Un registro por (distribuidor, grupo de producto, mes), **incluyendo explícitamente los ceros**. Si un distribuidor no devolvió nada de un grupo en un mes, la fila debe existir con `y = 0`. Omitirla es el error que más sesga estos modelos: el modelo deja de aprender cuándo *no* hay devolución.

Filtrar solo combinaciones "vivas": el distribuidor debía existir y el SKU debía estar dentro de su ciclo de vida (`Item Birth` / `Item Death`, con centinelas 1990 y 2075 tratados como nulos) en ese período.

## 7.2 Elección del grano temporal y de producto

### 7.2.1 Grano temporal — decisión condicionada por la ventana de 12 meses

Con 12 meses de target observado, el grano mensual deja **12 observaciones por serie**. Descontando los rezagos de 3 períodos quedan 9, que hay que repartir entre entrenamiento, validación y prueba. Es insuficiente para un modelo que aprenda dinámica temporal por serie, aunque el *pooling* transversal —el modelo aprende simultáneamente de las ~270 combinaciones distribuidor × grupo— mitiga parcialmente el problema. Tres vías, en orden de preferencia:

| Vía | Condición | Períodos por serie | Ventaja / costo |
|---|---|---|---|
| **A · Mensual extendido** | La reconstrucción retrospectiva (§5.6.1) pasa el criterio del 10 % | **24** | Preferida. Alinea el modelo con el ciclo de decisión del negocio y recupera el rezago anual y dos observaciones de cada campaña. Costo: parte del target es derivado, no observado |
| **B · Semanal** | La reconstrucción no pasa | **~52** | Cuadruplica las filas de entrenamiento y permite aprender dinámica. Costo: mayor intermitencia (más ceros) y desalineación con el ciclo mensual del negocio; se corrige agregando las predicciones semanales al mes |
| **C · Mensual simple** | Última opción | **12** | Solo viable apoyándose fuertemente en el *pooling* transversal y renunciando a estacionalidad. Documentar como limitación |

**Recomendación:** ejecutar primero la validación de §5.6.1. Si pasa, vía A. Si no pasa, vía B con reporte agregado a mes. La vía C solo si la vía B resulta demasiado dispersa según el análisis de intermitencia del paso E7 del EDA.

En cualquiera de las tres, **declarar explícitamente la limitación en el documento capstone**: la ventana de 12 meses de eventos impide validar estacionalidad anual, y esa es una restricción del dato, no del método.

### 7.2.2 Grano de producto

Con 269 SKUs × 45 distribuidores × período se generan ~12.000 series, casi todas mayoritariamente en cero.

1. Calcular por nivel jerárquico el **porcentaje de celdas con `y > 0`**, el **ADI** (intervalo medio entre demandas) y el **CV²**, y clasificar la intermitencia (suave / errática / intermitente / grumosa) según Syntetos-Boylan.
2. Elegir el nivel más granular cuya densidad supere ~30 % de celdas no nulas. Candidatos de mayor a menor granularidad: `Código del artículo` → `Product Family` → `GAMA` → `TIPO_MATERIAL` → segmento (SIM / Equipo).
3. Si el negocio exige SKU, modelar en el nivel denso y **desagregar top-down** con proporciones históricas, o reconciliar con MinT. Documentar la decisión y su costo en precisión.

Recomendación preliminar según la estructura observada: `TIPO_MATERIAL × distribuidor` o `GAMA × distribuidor`, reportando SKU por desagregación.

## 7.3 Calendario de campañas (respuesta P11 operacionalizada)

Día de la Madre en Ecuador = segundo domingo de mayo. Ventana de campaña = 30 días previos.

| Año | 2.º domingo de mayo | Ventana Día de la Madre | Ventana Navidad |
|---|---|---|---|
| 2024 | 12-may-2024 | 12-abr a 12-may-2024 | 24-nov a 24-dic-2024 |
| 2025 | 11-may-2025 | 11-abr a 11-may-2025 | 24-nov a 24-dic-2025 |
| 2026 | 10-may-2026 | 10-abr a 10-may-2026 | 24-nov a 24-dic-2026 |

Variables derivadas para `dim_calendario`:

- `en_campania` (binaria), `tipo_campania` (madre / navidad / ninguna)
- `dias_a_inicio_campania` y `dias_desde_fin_campania` — **esta última es probablemente la variable más predictiva del proyecto**: la devolución es un fenómeno *posterior* a la campaña, cuando el distribuidor no colocó el sobre-stock que pidió anticipándose a ella.
- `mes_post_campania` (binaria, mes inmediatamente siguiente al cierre)

**Consecuencia de la ventana de 12 meses (N10).** Con el target observado directamente, cada campaña se observa **una sola vez**: una Navidad y un Día de la Madre. Eso significa que:

- El rezago `y[t-12]` **no existe** y debe eliminarse del conjunto de variables.
- Las variables de mes calendario (*dummies* o codificación cíclica) capturarían una única realización de cada mes: el modelo memorizaría en lugar de generalizar. **Sustituirlas por las variables de proximidad a campaña**, que sí se repiten y son interpretables.
- Si la extensión retrospectiva de §5.6.1 tiene éxito, se recuperan dos observaciones de cada campaña y el rezago anual vuelve a ser utilizable; aun así, dos observaciones permiten estimar el efecto pero no validarlo con robustez.

Declararlo como limitación explícita en el documento capstone.

## 7.4 Ingeniería de variables

Todas calculadas con ventana hasta el cierre de *t*, sin excepción.

**Historia del target**
: rezagos `y[t-1]`, `y[t-2]`, `y[t-3]` (el rezago `y[t-12]` **solo si la extensión retrospectiva de §5.6.1 tiene éxito**, N10); medias y desviaciones móviles de 3, 6 y 12 períodos; tasa histórica de devolución del distribuidor (Σdevoluciones / Σpedidos) a 3, 6 y 12 meses; tasa histórica del SKU transversal a distribuidores; pendiente OLS de las últimas 6 observaciones.

**Inventario y flujo** *(donde se concentra el poder explicativo del problema)*
: stock del distribuidor al cierre de *t*; **días de inventario (DOH)** = stock / venta diaria promedio de 30 días; **antigüedad del stock** en *buckets* 0-30 / 31-60 / 61-90 / >90 días, derivada del primer snapshot en que la unidad aparece en la bodega (equipos) o del campo `Lote` (SIMs), más percentiles p50 y p90; brecha acumulada *sell-in* − *sell-out* a 3 y 6 meses (proxy cuantitativo del "sobrepedido sistemático" del Ishikawa); porcentaje de unidades en condición `Obsoleto`; porcentaje en `Reservado` y `En Tránsito`.

**Comportamiento de pedido** *(habilitado por `ReporteLogistica`)*
: ***fill rate*** = `RECEIVED_QUANTITY` / `APPROVED_QUANTITY` —exploratorio, ya que P17 señala que solo `APPROVED_QUANTITY` es contable, pero la brecha entre aprobado y recibido sigue siendo una señal de comportamiento—; número de órdenes por mes; tamaño medio de orden; volatilidad del tamaño de orden; días entre órdenes consecutivas; ratio de transferencias entre bodegas sobre pedidos —excluidas del target pero conservadas como predictor (§6.2)—, porque un distribuidor que redistribuye mucho internamente está corrigiendo una asignación inicial equivocada; número de cortes en que la línea permaneció abierta, como proxy del tiempo de tránsito.

**Cupo y capacidad**
: valor del cupo, tipo de cupo, flag `Aplicar Cupo`, número de bodegas del distribuidor, dispersión geográfica. *(Estático, por P7.)*

**Figura comercial y estado (nuevas en v4)**
: `MO_TYPE` (`Consignación` frente a `Venta al Partner`) como variable de primer orden o como criterio de segmentación en modelos separados (N13); `TYPE_`; participación histórica de cada figura en el mix del distribuidor; `%_submitted_al_corte` del período como variable de control de la censura (N11).

**Atributos de producto**
: `Unit Cost`, `GAMA`, `TIPO_MATERIAL`, `PROVEEDOR`; antigüedad del SKU (`t` − `Item Birth Date`); días hasta fin de vida; flag "tiene sustituto o equivalente"; `PRIORIDAD_CUPOS`; `Seasonality Group Code`.

**Geografía y canal**
: región, provincia, ciudad, `CATEGOTIZACION`, `Canal`, `Tipo de BU`, `Zona Courier`, categoría de días de entrega desde el centro de distribución.

**Calendario**
: mes, trimestre, codificación cíclica seno/coseno; feriados de Ecuador; variables de campaña de §7.3.

**Codificación de categóricas** (nodo 3.1.3 del mapa metodológico): usar el soporte nativo de categóricas de XGBoost/LightGBM, o *target encoding* calculado **solo dentro de cada pliegue de entrenamiento**. El one-hot sobre 45 distribuidores × 269 SKUs no escala. Agrupar categorías raras (< 1 % de frecuencia) en `OTROS` y definir el comportamiento ante categorías no vistas en producción.

## 7.5 Partición y validación

**Prohibido el *split* aleatorio.** El mapa metodológico recomienda partición estratificada preservando distribución; esa recomendación aplica a datos independientes e idénticamente distribuidos. **En pronóstico temporal, la partición estratificada aleatoria es en sí misma una fuga de información** — precisamente el error que advierte el nodo 4 del mismo mapa. La reconciliación correcta es: partición **temporal**, estratificada solo en el sentido de verificar que los tres conjuntos mantengan representatividad de distribuidores y zonas.

```
Vía A — mensual extendido (24 períodos):
|————————— train —————————|——— valid ———|——— test ———|
        ~20 meses             2 meses       2 meses

Vía B — semanal (~52 períodos):
|————————— train —————————|——— valid ———|——— test ———|
        ~40 semanas           6 semanas     6 semanas

Vía C — mensual simple (12 períodos):
|——— train ———|— valid —|— test —|
    8 meses      2 meses   2 meses
                          ↑ intacto hasta la evaluación final
```

Con la vía C, dos meses de prueba equivalen a menos del 17 % del histórico y la estimación del error tendrá una incertidumbre alta. En ese escenario, **reportar el resultado del *backtesting* con origen rodante como métrica principal** en lugar de un único *holdout*, y acompañar cada métrica de un intervalo de confianza obtenido por remuestreo en bloques. Presentar un MAPE puntual sobre 2 meses y 12 observaciones por serie como si fuera una estimación precisa sería un error de interpretación visible en la defensa.

- Validación cruzada con `TimeSeriesSplit`, origen rodante y ventana expansiva, mínimo 3 pliegues.
- *Backtesting*: reentrenar en cada origen y predecir h pasos adelante, replicando condiciones reales de uso.
- El conjunto de prueba se toca **una sola vez**. Si se ajusta algo después de mirarlo, deja de ser prueba.
- **Revisión obligatoria de fuga**: para cada variable, verificar que su cálculo no usa registros con fecha posterior a *t*. Un R² sospechosamente alto en el primer intento casi siempre es fuga, no talento.

## 7.6 Modelos

| Nivel | Modelo | Propósito |
|---|---|---|
| 0 | Naive (`y[t+1] = y[t]`) y Seasonal Naive | Piso absoluto. Si el modelo final no lo supera con holgura, no hay proyecto |
| 0b | Media móvil 3 meses · **Croston / SBA / TSB** | Baselines diseñados para demanda intermitente. Es el rival real, no el naive |
| 1 | GLM Poisson / Tweedie regularizado | Referencia lineal interpretable; mide cuánto aporta la no linealidad |
| 2 | **Random Forest Regressor** | Comprometido en el Objetivo Específico 3 |
| 3 | **XGBoost** con `objective="count:poisson"` o `reg:tweedie` | Comprometido. El objetivo por defecto `reg:squarederror` es **inadecuado** para conteos con exceso de ceros: produce predicciones negativas y sesga hacia la media |
| 4 *(opcional)* | XGBoost cuantílico (α = 0,8) | Predicción conservadora coherente con el riesgo asimétrico de §4 |

**Tuning:** `RandomizedSearchCV` sobre `TimeSeriesSplit` con `early_stopping_rounds`. Espacio inicial para XGBoost: `n_estimators` 200–1500, `max_depth` 3–8, `learning_rate` 0,01–0,2, `subsample` 0,6–1,0, `colsample_bytree` 0,6–1,0, `min_child_weight` 1–20, `reg_lambda` 0–10.

**Normalización** (nodo 5 del mapa metodológico): Random Forest y XGBoost **no la requieren**. Solo aplica al GLM del nivel 1, y sus parámetros deben ajustarse **exclusivamente sobre el conjunto de entrenamiento** y aplicarse mediante `Pipeline` de scikit-learn para que la transformación se reajuste dentro de cada pliegue de validación cruzada.

## 7.7 Métricas — y una corrección al criterio de éxito

El documento fija **MAPE ≤ 15 %**. Con series intermitentes esto es técnicamente problemático: el MAPE divide por el valor real y, cuando el real es 0, el término es indefinido o infinito. Un modelo excelente puede reportar MAPE = ∞.

| Métrica | Nivel de cálculo | Rol |
|---|---|---|
| **MAPE** | Agregado a **distribuidor × mes** | Cumple el criterio comprometido; es además el nivel en que el negocio decide |
| **WMAPE** (Σ\|e\| / Σy) | Grano completo | **Métrica principal.** Robusta a ceros; se lee como "% de error sobre el volumen total" |
| **MAE** | Grano completo | Comprometida; en unidades físicas |
| **RMSE** | Grano completo | Comprometida; penaliza errores grandes |
| **MASE** | Grano completo | Comparación honesta contra el baseline (MASE < 1 = el modelo aporta) |
| **Sesgo (ME)** y **% de subestimación** | Por distribuidor y en meses de alta devolución | Operacionaliza la "métrica de riesgo" declarada en el alcance |
| **Pinball loss** | Si se usa el modelo cuantílico | Evalúa la predicción conservadora |

**Precaución adicional por la censura (N11).** Las métricas deben calcularse sobre la ventana truncada en *T* días. Reportar un WMAPE que incluya los últimos días, donde una parte de las devoluciones aún no se ha consumado, produce un error artificialmente favorable en apariencia —el modelo predice más de lo observado y el observado está incompleto— o desfavorable, según el signo del sesgo. En cualquier caso, no es el error real. Verificar además que el error no correlacione con `%_submitted_al_corte`.

Redacción sugerida para el documento capstone: *"el MAPE máximo del 15 % se verifica sobre la agregación distribuidor-mes, nivel en el que se toma la decisión de planificación; a nivel de SKU se reporta WMAPE y MASE, por tratarse de series intermitentes en las que el MAPE no está definido."* Es una precisión metodológica que fortalece el trabajo.

## 7.8 Explicabilidad (SHAP)

- **Global:** `summary_plot` (beeswarm) para el ranking de variables; `dependence_plot` para las cinco principales. Esto **cierra el Objetivo Específico 1**, que exige identificar al menos dos variables asociadas a la devolución.
- **Local:** *waterfall* por caso — "por qué el modelo predice 340 unidades para el distribuidor X en octubre". Es lo que hace el modelo defendible frente a los distribuidores, según el argumento ético del documento.
- **Consistencia:** contrastar el ranking SHAP con las causas del Ishikawa. Si el sobrepedido acumulado, el DOH y los días transcurridos desde el fin de campaña aparecen arriba, hay convergencia entre el diagnóstico cualitativo y la evidencia cuantitativa — un hallazgo potente para Resultados y Discusión.

## 7.9 Auditoría de sesgo y equidad

1. **Representatividad:** número de observaciones por distribuidor, provincia y categorización; índice de concentración (Gini o HHI).
2. **Error desagregado:** WMAPE y sesgo por región, por `CATEGOTIZACION`, por tercil de cupo y por canal.
3. **Criterio de aprobación:** el WMAPE del peor grupo no debe exceder en más de 1,5× al del mejor. Si lo excede, aplicar reponderación (`sample_weight`) o modelos segmentados, y documentarlo.
4. Verificar explícitamente que el modelo **no subestime sistemáticamente** la devolución en zonas con menos historia: eso trasladaría el costo de la incertidumbre a los distribuidores pequeños, que es el riesgo ético advertido en el alcance (Mehrabi et al., 2021).

## 7.10 Puertas de calidad (CRISP-ML(Q))

| Fase | No se avanza hasta que… |
|---|---|
| 1 · *Business & Data Understanding* | Ficha de §4 firmada; P13–P18 respondidas; catálogo de bodegas centrales confirmado |
| 2 · *Data Engineering* | Validaciones en verde 3 días seguidos; huérfanos en *joins* < 1 %; conciliación A vs B con desvío < 5 %; eventos `OTRO` < 2 %; diccionario de datos publicado |
| 3 · *ML Model Building* | MASE < 1 frente a Croston/SBA en validación; revisión de fuga sin hallazgos; experimentos registrados en MLflow |
| 4 · *Model Evaluation* | MAPE agregado ≤ 15 % en prueba; WMAPE y MASE reportados; equidad aprobada; SHAP revisado con el área de planificación |
| 5 · *Deployment* | Piloto acordado; tablero validado por el usuario; predicciones registradas en log |
| 6 · *Monitoring* | Umbrales de *drift* definidos; política de reentrenamiento documentada |

---

# 8. Análisis Exploratorio de Datos: organización, paso a paso y herramientas

Esta sección desarrolla el nodo **3.1.1 (Análisis Exploratorio)** del mapa metodológico, aterrizado a las particularidades de este proyecto: volumen muy alto, múltiples fuentes heterogéneas, naturaleza temporal y variable objetivo intermitente.

## 8.1 Principio de organización: el EDA se hace por capas, no de una vez

El error más común es intentar un único EDA monolítico sobre "los datos". Aquí hay tres preguntas distintas que requieren tres EDA distintos:

| EDA | Sobre qué | Pregunta que responde | Cuándo |
|---|---|---|---|
| **EDA-1 · Técnico** | Cada archivo en bronze, por separado | ¿El dato llegó bien? ¿Tipos, faltantes, rangos, duplicados? | Durante la ingesta, automatizado |
| **EDA-2 · Integración** | Relaciones entre tablas (silver) | ¿Los *joins* cierran? ¿La conciliación A vs B cuadra? ¿Hay huérfanos? | Tras construir silver |
| **EDA-3 · Analítico** | Panel gold (distribuidor × grupo × mes) | ¿Qué explica la devolución? ¿Qué forma tiene el target? | Antes de modelar — **este es el que cierra el Objetivo Específico 1** |

**Regla de volumen:** EDA-1 sobre 2.000.000 de filas/día no se hace con herramientas de escritorio. Se hace con SQL sobre parquet (DuckDB) o con Polars, y se **materializa un extracto representativo** sobre el cual sí se usan herramientas visuales. El panel gold, en cambio, tendrá del orden de miles a decenas de miles de filas: cabe perfectamente en jamovi, Orange o Excel.

## 8.2 Paso a paso

### E0 · Preparar el banco de trabajo del EDA
Antes de mirar nada, construir tres extractos reproducibles y versionados:

- **Muestra técnica:** 7 días consecutivos completos de cada fuente (para EDA-1).
- **Muestra de integración:** un mes completo con todas las tablas cruzadas (para EDA-2).
- **Panel completo:** la tabla gold de 24 meses (para EDA-3).

Cada extracto se genera con un *script* versionado, no manualmente. Esto satisface el nodo 7 (Reproducibilidad) del mapa metodológico y evita el hallazgo irreproducible que aparece en una captura de pantalla y nadie puede volver a obtener.

### E1 · Perfilado automático por tabla *(EDA-1)*
Ejecutar un perfilado automatizado por cada fuente. Salida esperada: tipos inferidos vs. declarados, porcentaje de faltantes por columna, cardinalidad, valores más frecuentes, alertas de constantes y de alta correlación.

- **Herramienta:** `ydata-profiling` (antes *pandas-profiling*) en modo `minimal=True` para tablas anchas.
- **Artefacto:** un HTML por tabla en `reports/eda/perfilado/`.
- **Qué buscar aquí específicamente:** que `?`, `"NULL"`, `=""` y cadenas vacías aparezcan como los valores frecuentes que son, y no pasen desapercibidos como categorías legítimas.

### E2 · Auditoría de llaves e integridad referencial *(EDA-2)*
Para cada *join* de la tabla de §5.5, calcular: cardinalidad real (1:1, 1:N, N:M), porcentaje de filas huérfanas en cada dirección, y listado de las 20 llaves huérfanas más frecuentes.

- **Herramienta:** DuckDB con SQL (`ANTI JOIN`), por volumen.
- **Artefacto:** tabla de integridad referencial con semáforo por *join*.
- **Umbral:** > 1 % de huérfanos exige explicación documentada antes de continuar.

### E3 · Cobertura temporal
Verificar que la secuencia diaria de los 24 meses no tenga huecos: contar archivos por mes, detectar fechas faltantes, y graficar el número de filas por día por fuente.

- **Qué revela:** días sin extracción (rompen el *diff*), truncamientos de extracción, y cambios de proceso en el origen (un salto de nivel en el conteo diario suele indicar un cambio de sistema, no un cambio de negocio).
- **Visual:** gráfico de líneas de filas/día, con banda de ±3σ.

### E3b · Verificación de deduplicación y de la ventana de solapamiento
Dos comprobaciones específicas de esta versión, previas a cualquier análisis del target:

- **Consolidación de cortes:** verificar el solapamiento intra-día (debe ser ≈ 0, según P20) y medir la reaparición de líneas entre días, que es además el insumo para estimar el tiempo hasta el cierre (§5.5.1).
- **Censura a la derecha:** graficar el porcentaje de líneas en `Submitted` por mes de `CREATED_WHEN`. La curva debe crecer bruscamente en los últimos períodos; el punto donde se estabiliza indica el valor de *T* con que truncar la ventana del target (N11). **Sin esta verificación, los meses de validación y prueba estarán sesgados a la baja.**
- **Solapamiento de fuentes:** cuantificar, mes a mes, la concordancia entre la fuente A (eventos) y la fuente B (snapshots) durante los 12 meses en que ambas existen. Es el insumo directo de la decisión de §5.6.1 y debe hacerse **antes** de construir el panel, porque determina si el panel tendrá 12 o 24 períodos.

### E4 · Análisis de valores faltantes *(nodo 3.1.2 del mapa)*
Para cada tabla: porcentaje de ausencia por columna, **patrón** de ausencia (¿aleatorio o estructural?), y correlación entre ausencias.

- **Herramienta:** `missingno` (matriz, mapa de calor y dendrograma).
- **Decisión documentada por columna:** imputar, eliminar o **marcar**. En este proyecto la tercera opción es a menudo la correcta: que `ARTICLE` esté vacío no es ruido, es información sobre cómo se registró la orden. Crear `articulo_faltante` como variable binaria antes de imputar.
- **Regla:** nunca imputar con estadísticos calculados sobre el conjunto completo — se hace dentro del `Pipeline`, ajustado solo en entrenamiento (nodo 4, *data leakage*).

### E5 · Variables categóricas *(nodo 3.1.3 del mapa)*
Por cada categórica: cardinalidad, distribución de frecuencias, cola de categorías raras, y consistencia de valores entre fuentes (`ESIM DIGITAL` vs `esim digital` vs `ESIM  DIGITAL` con doble espacio).

- **Qué buscar:** valores centinela disfrazados de categoría (`OTRAS`, `OTROS`, `?`), variantes de capitalización y espacios, y categorías que aparecen o desaparecen a lo largo de los 24 meses — esto último es *drift* de catálogo y afectará al modelo en producción.
- **Artefacto:** diccionario de categorías normalizado, que alimenta el dominio cerrado de los contratos de datos.

### E6 · Valores atípicos y rangos
Boxplots y percentiles por variable numérica; conteo de valores fuera de rango físico (costos negativos, cantidades recibidas mayores que aprobadas).

- **Distinguir dos tipos:** el atípico **erróneo** (costo = 0 en un equipo de gama alta) se corrige o se marca; el atípico **legítimo** (una devolución masiva de 5.000 unidades tras una campaña fallida) **es exactamente el fenómeno que el proyecto quiere predecir** y no debe eliminarse. Esta distinción debe quedar documentada: eliminar los picos de devolución "por ser outliers" destruiría el valor del modelo.
- **Herramienta:** Orange (widget *Box Plot* + *Outliers*) para inspección visual rápida; `scipy`/`numpy` para el cálculo formal.

### E7 · Caracterización del target *(EDA-3 — el paso central)*
Sobre el panel gold:

- Histograma de `y`; **porcentaje de celdas en cero** por nivel de agregación.
- **ADI** y **CV²** por serie, con clasificación Syntetos-Boylan en el plano ADI-CV².
- Comparación del porcentaje de ceros entre niveles jerárquicos (SKU → familia → gama → tipo de material) para **decidir el grano de modelado** (§7.2).
- Distribución del target por segmento (SIM vs equipo): probablemente requieran modelos separados.
- **Separar el análisis por `MO_TYPE`** (`Consignación` frente a `Venta al Partner`): comparar tasa de devolución, distribución del target y perfil de intermitencia. Si difieren de forma marcada, la decisión de entrenar modelos separados (N13) se toma aquí y no después.
- **Repetir el análisis de intermitencia en grano semanal y mensual.** La comparación de ADI y CV² entre ambos granos, junto con el resultado de E3b, es lo que cierra la decisión de vía temporal de §7.2.1.

**Artefacto decisivo:** la tabla "nivel jerárquico vs. densidad de no-ceros". De ella sale la decisión de grano, que condiciona todo el modelado posterior.

### E8 · Análisis temporal
- Serie agregada total de devoluciones por mes; descomposición **STL** (tendencia, estacionalidad, residuo).
- **ACF y PACF** para identificar la memoria de la serie y justificar qué rezagos incluir como variables.
- Superposición del calendario de campañas (§7.3) sobre la serie: verificar visualmente el desfase entre pico de pedido y pico de devolución. **Cuantificar ese desfase medio es uno de los hallazgos más valiosos que puede producir el EDA**, porque define el horizonte de predicción útil.
- Prueba de estacionariedad (ADF) sobre la serie agregada.

- **Herramienta:** `statsmodels` para STL/ACF/PACF/ADF; el *add-on* **Timeseries de Orange** si se prefiere flujo visual.

### E9 · Análisis transversal y de representatividad
- Distribución del volumen de devolución por distribuidor: curva de Pareto (¿el 20 % de distribuidores concentra el 80 % de las devoluciones?).
- Tasa de devolución (devoluciones / pedidos) por región, por `CATEGOTIZACION`, por canal, por gama.
- Número de observaciones por grupo → insumo directo de la **auditoría de equidad** (§7.9).
- Mapa o gráfico de barras por provincia.

**Este paso es obligatorio, no opcional:** el alcance del documento compromete explícitamente evaluar si el histórico sobre-representa a determinados distribuidores o zonas. Aquí es donde esa evaluación se hace.

### E10 · Relación entre variables y target
- **Correlación de Spearman** (no Pearson): la relación esperada entre DOH y devolución es monótona pero no lineal.
- **Información mutua** (`mutual_info_regression`) para capturar relaciones no monótonas.
- Gráficos de dispersión de las 10 variables principales contra `y`, con línea de tendencia.
- Matriz de correlación entre predictoras para detectar multicolinealidad (relevante para el GLM, menos para los árboles).

- **Salida:** ranking preliminar de variables. Se contrastará después con el ranking SHAP del modelo entrenado; la coincidencia o divergencia entre ambos es material para la discusión.

### E11 · Análisis del ciclo de devolución
Específico de este proyecto y difícilmente automatizable: para las unidades con trazabilidad completa (equipos con IMEI), calcular el **tiempo transcurrido entre el despacho al distribuidor y su retorno**.

- Histograma y curva de supervivencia (Kaplan-Meier) del tiempo hasta la devolución.
- Comparación por gama, por distribuidor y por campaña.
- **Para qué sirve:** determina el horizonte de predicción realista. Si la mediana del ciclo es de 45 días, predecir a un mes es adecuado; si es de 120 días, el horizonte debe extenderse y las variables de antigüedad del stock ganan peso.

### E12 · Consolidación de hallazgos
Documento de hallazgos del EDA (`reports/eda/hallazgos.md`) con: las **dos o más variables con mayor relación con la devolución** (cierra el Objetivo Específico 1), la decisión de grano, la decisión sobre faltantes por columna, las anomalías encontradas y las implicaciones sobre el modelado.

Este documento es un anexo directo del capstone y el insumo de la reunión de validación con el área de planificación de demanda.

## 8.3 Herramientas recomendadas

### Herramientas con interfaz gráfica

| Herramienta | Fortaleza en este proyecto | Límite práctico | Recomendación |
|---|---|---|---|
| **jamovi** | Estadística descriptiva, correlaciones, ANOVA y regresión con **salidas en formato APA directamente citables en el informe**. Gratuito, basado en R | En memoria; cómodo hasta ~100.000–500.000 filas | ✅ **Recomendado para EDA-3** sobre el panel gold. Es la herramienta que mejor rentabiliza el tiempo para la redacción del capstone |
| **Orange** (Univ. de Ljubljana) | Flujo visual de *widgets*; excelente para exploración visual, *Scatter Plot* con ranking automático de pares informativos, correlogramas, *Box Plot*, *Distributions*. *Add-on* **Timeseries** para STL y ACF. Permite prototipar Random Forest sin código | Similar a jamovi | ✅ **Recomendado para EDA-3 visual y para la defensa**: el flujo de *widgets* se muestra como diagrama y comunica muy bien el *pipeline* |
| **JASP** | Alternativa a jamovi, con énfasis en estadística bayesiana | Similar | ⚪ Opcional; solo si el equipo quiere contrastes bayesianos |
| **KNIME Analytics Platform** | ETL visual de mayor escala; lee parquet; nodos de calidad de datos | Más pesado, mayor curva de aprendizaje | 🟡 Alternativa si el equipo prefiere evitar código en la capa de integración (EDA-2) |
| **Power BI** | Ya está en el *stack* de la Propuesta A; ideal para compartir el EDA **con el cliente** y para el tablero final | No es herramienta de análisis estadístico | ✅ **Recomendado para la validación con el área de planificación** |

### Herramientas en código (Python)

| Librería | Uso en este proyecto | Paso |
|---|---|---|
| **DuckDB** | SQL directo sobre parquet; permite explorar 1.460 M de registros sin *cluster*. Es lo que hace viable el EDA-1 a escala | E1–E3 |
| **Polars** | Ingesta y agregación *lazy* de los snapshots de SIMs | E0–E1 |
| **ydata-profiling** | Perfilado automático HTML por tabla | E1 |
| **missingno** | Matriz, mapa de calor y dendrograma de faltantes | E4 |
| **sweetviz** | Comparación entre dos conjuntos (train vs test, mes A vs mes B) — muy útil para detectar *drift* entre períodos del histórico | E3, E5 |
| **D-Tale** | Exploración interactiva tipo hoja de cálculo sobre un DataFrame | E6–E10 |
| **statsmodels** | STL, ACF/PACF, ADF, regresión de referencia | E8 |
| **sktime** / **statsforecast** | Cálculo de ADI y CV², clasificación de intermitencia, baselines Croston/SBA/TSB | E7, modelado |
| **lifelines** | Curva de supervivencia del tiempo hasta la devolución | E11 |
| **pandera** / **Great Expectations** | Validación automática contra el contrato de datos | E1, continuo |
| **matplotlib / seaborn** | Figuras finales para el documento (control total del formato) | E7–E12 |

### Recomendación de combinación

Para un equipo de tres personas con 7 semanas:

1. **DuckDB + Polars + ydata-profiling + missingno** para EDA-1 y EDA-2 (automatizado, reproducible, versionado).
2. **jamovi u Orange** sobre el panel gold para EDA-3, aprovechando la velocidad de exploración visual y las salidas listas para el informe.
3. **matplotlib/seaborn** solo para las figuras definitivas que irán al documento.
4. **Power BI** para la sesión de validación con el cliente.

Evitar la trampa de dedicar tiempo a dominar cuatro herramientas nuevas. Orange y jamovi se aprenden en una tarde; KNIME no. Si el tiempo aprieta, jamovi sobre el panel gold es suficiente y es la opción de mejor relación esfuerzo-resultado para un trabajo de titulación.

---

# 9. Integración con la demanda neta y piloto

## 9.1 Cálculo del ajuste

```
DemandaNetaAjustada[d, s, t+1] = Pedido[d, s, t+1] − α[d,s] · ŷ[d, s, t+1]
```

- **α (factor de confianza)** por celda: donde el error histórico del modelo es alto, amortiguar el ajuste en lugar de restar el 100 % de la predicción. Evita que un error del modelo se traduzca en desabastecimiento.
- Restringir `DemandaNetaAjustada ≥ 0` y no superar el cupo disponible.
- Exponer siempre **las tres cifras** al planificador: pedido original, devolución esperada y demanda ajustada. Nunca entregar solo el número final: la adopción depende de que el usuario pueda auditar el ajuste.

## 9.2 Diseño del piloto (Objetivo Específico 5)

El objetivo compromete una reducción de al menos 10 % en la desviación entre demanda proyectada y demanda neta real.

- **Grupo piloto:** 8–12 distribuidores seleccionados por estratificación (región × categorización × tercil de cupo), no por conveniencia.
- **Grupo de control:** distribuidores comparables sin ajuste, para permitir atribución causal en lugar de comparación antes/después.
- **Métrica de impacto:** MAPE de la proyección de demanda con ajuste vs. sin ajuste, sobre el mismo período.
- **Refuerzo por *backtesting* contrafactual:** con 24 meses de histórico disponibles, aplicar el ajuste retrospectivamente sobre períodos ya cerrados y medir la reducción de desviación que se habría obtenido. Esto **ya no es un plan B** como en la v1: con el histórico confirmado, es evidencia sólida que complementa el piloto y no depende de observar un ciclo completo de devolución dentro de la ventana del proyecto.

---

# 10. MLOps y monitoreo

Alcance proporcional a la Propuesta A; no requiere infraestructura en la nube.

- **Registro de predicciones:** cada corrida persiste fecha, versión de modelo, entradas y predicción. Sin este log no hay monitoreo posible.
- **Drift de datos:** PSI o prueba KS mensual sobre las 10 variables principales; alerta si PSI > 0,2.
- **Drift de concepto:** WMAPE rodante de 3 meses; alerta si se degrada más de 20 % respecto del valor de prueba.
- **Política de reentrenamiento:** trimestral programado, más disparo por alerta de *drift*. Documentar el criterio de promoción: el modelo nuevo debe superar al vigente sobre el mismo *holdout*.
- **Registro de modelos:** MLflow Model Registry con estados *Staging* / *Production* / *Archived*.
- **Hoja de ruta a la Propuesta B:** dejar escrito qué componente migraría primero a la arquitectura de reentrenamiento continuo y bajo qué condición de negocio. Alimenta la sección "Trabajo futuro" del documento.

---

# 11. Estructura de repositorio y *stack*

```
capstone-g5-devoluciones/
├── README.md
├── Makefile                  # backfill / ingest / eda / features / train / evaluate
├── requirements.txt          # versiones ancladas
├── .env.example              # sal de hashing y rutas (el .env real NO se versiona)
├── .pre-commit-config.yaml   # detector de PII + black + ruff
├── dvc.yaml
├── contracts/                # 7 contratos de datos en YAML
├── conf/
│   ├── config.yaml           # grano, horizonte, semilla, ventanas
│   └── model_params.yaml
├── src/
│   ├── ingest/               # lectores, parsers de fecha (3 convenciones), limpieza
│   ├── backfill/             # descubrimiento de archivos, paralelización, manifiesto
│   ├── quality/              # esquemas pandera, reportes de calidad
│   ├── events/               # clasificación de eventos, diff de snapshots, conciliación
│   ├── features/             # panel, calendario de campañas, feature engineering
│   ├── models/               # baselines, RF, XGBoost, tuning
│   ├── evaluate/             # métricas, backtesting, equidad, SHAP
│   └── serve/                # exportación para Power BI
├── notebooks/                # SOLO exploración; nada productivo vive aquí
├── tests/                    # pytest: transformaciones, joins, ausencia de fuga temporal
├── reports/
│   ├── quality/              # reportes de calidad fechados
│   ├── eda/                  # perfilados, figuras, hallazgos.md
│   └── model_card.md
└── docs/
    ├── diccionario_datos.md
    ├── decisiones.md         # registro de decisiones (ADR) — clave en la defensa
    └── actas_cliente.md
```

**Stack:** Python 3.11+ · Polars o pandas + DuckDB · scikit-learn · xgboost · shap · statsmodels · sktime · pandera · mlflow · dvc · matplotlib/seaborn · jamovi u Orange para EDA-3 · Power BI para el tablero.

Sobre Polars frente a pandas: dado el volumen de SIMs, Polars con ejecución *lazy* y `sink_parquet` procesa 2 M de filas por día sin cargar todo en memoria. La alternativa es DuckDB con SQL directo sobre los parquet, igualmente válida y con menor curva si el equipo prefiere SQL. Ambas son defendibles; elegir una y ser consistente.

---

# 12. Trazabilidad con el mapa "Fundamentos para Proyectos de IA"

| Nodo del mapa | Sección de este plan |
|---|---|
| 1. Propósito y objetivos de aprendizaje | §0, §4 |
| 2. Diseño estructurado (pipeline como columna vertebral) | §5.1 |
| 3. Pipeline de datos · Componentes esenciales | §5.1, §5.2, §11 |
| 3. Pasos del pipeline · Ingesta (CSV, bases, APIs; validación y documentación) | §5.2, §5.3, §5.4, §5.7 |
| 3.1 Limpieza y preprocesamiento | §5.5.1 (deduplicación), §5.7, §8.2 (E3b–E6) |
| 3.1.1 Análisis exploratorio (EDA) | **§8 completa** |
| 3.1.2 Manejo de valores faltantes | §8.2 · E4 |
| 3.1.3 Variables categóricas | §7.4 (codificación), §8.2 · E5 |
| 3. Partición de conjuntos | §7.5 — **con la adaptación temporal explicada abajo** |
| 3. Entrenamiento del modelo | §7.6 |
| 3. Evaluación de resultados | §7.7, §7.9 |
| 3. Registro y documentación | §5.9, §10 |
| 4. Error crítico: data leakage | §7.5 (revisión obligatoria), §7.4 (*target encoding* por pliegue), §7.6 (normalización dentro del `Pipeline`) |
| 5. Normalización y estandarización | §7.6 — no aplica a árboles; sí al GLM |
| 6 / 6.1 Modelo baseline como referencia | §7.6 niveles 0 y 0b |
| 7 / 7.1 Reproducibilidad técnica y ética | §5.1, §5.9, §5.8 |
| 8. Flujo completo de datos crudos a baseline | §6.1 |

**Una adaptación necesaria.** El mapa recomienda partición *estratificada preservando distribución*. Esa recomendación es correcta para datos independientes e idénticamente distribuidos, pero **en pronóstico temporal una partición aleatoria estratificada constituye ella misma una fuga de información** — el error que el propio nodo 4 del mapa señala como crítico. La adaptación aplicada aquí es partición **temporal**, conservando del criterio de estratificación la verificación de que entrenamiento, validación y prueba mantengan representatividad de distribuidores y zonas geográficas. Dejar esta adaptación documentada en el capstone demuestra comprensión del marco, no desviación de él.

---

# 13. Matriz de riesgos actualizada

| ID | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Histórico insuficiente | ~~Alta~~ **Cerrado** | — | Confirmado por P2 |
| R2 | Target no observable | ~~Media~~ **Cerrado** | — | Resuelto por `ReporteLogistica` + doble fuente |
| R3 | Pedidos no disponibles | ~~Media~~ **Cerrado** | — | Resuelto por P3 |
| R4 | Nomenclatura real difiere de la declarada | ~~Alta~~ **Cerrado** | — | Confirmados N1, N2 y N3 en v3 |
| R5 | Mapeo SKU de SIMs no se cierra (N7) | **Media** | Alto | Derivar de `ARTICLE` en el histórico; si falla, modelar SIMs a nivel de `Modelo` sin cruzar Masterfile y documentar la limitación |
| R14 | Conteo múltiple del target por los 3 cortes | ~~Alta~~ **Baja** | Crítico | Confirmado en P20 que los cortes son incrementales. Se conservan las dos verificaciones ligeras de §5.5.1 |
| **R15** | **Ventana de 12 meses insuficiente para el grano mensual (N9)** | **Alta** | **Alto** | Extensión retrospectiva validada (§5.6.1); si no pasa, vía semanal (§7.2.1); reportar *backtesting* rodante con intervalos en lugar de un *holdout* único |
| **R16** | **Fallo o interrupción de la entrega por correo (B9)** | Media | Alto | Manifiesto con hash por adjunto, verificación de integridad, registro de cobertura; solicitar canal SFTP (P22) |
| **R17** | La reconstrucción retrospectiva introduce ruido en la mitad antigua del target | Media | Medio | Criterio de aceptación fijado **antes** de mirar resultados; variable `target_origen`; métricas por separado. P23 confirma que no hay días faltantes, lo que reduce la probabilidad |
| **R18** | **Censura a la derecha sesga validación y prueba (N11)** | **Alta** | **Alto** | Truncar la ventana en *T* = p95 del tiempo hasta el cierre; variable de control `%_submitted_al_corte`; verificación E3b antes de modelar |
| **R19** | **Pérdida del histórico: reside en un disco local con buzón sin retención (N14)** | Media | **Crítico** | **Copia masiva completa en la primera semana** a almacenamiento del equipo, con verificación por hash; solicitar respaldo al cliente (P29) |
| **R20** | `EQUIPMENT_ID` no es unitario y la vía del SKU se cae (N12) | Media | Alto | Prueba empírica de tasa de coincidencia antes de comprometer el diseño; alternativa: modelar SIMs por `Modelo` sin cruzar Masterfile |
| **R21** | Consignación y venta al partner se modelan como un solo fenómeno (N13) | Media | Medio | Segmentación obligatoria en E7; decisión de modelos separados tomada con evidencia |
| **R22** | Exposición de datos personales por el canal de correo | Media | Alto | Medidas compensatorias de §5.8.1; seudonimización en el primer punto bajo control; purga del buzón tras ingesta |
| R6 | *Backfill* más lento de lo estimado | Media | Medio | Estrategia de dos olas (§5.4); la ola 1 desbloquea el EDA y el baseline |
| R7 | Series demasiado intermitentes en todo nivel | Media | Alto | Agregar a `TIPO_MATERIAL` o segmento; objetivo Tweedie; reportar WMAPE y MASE |
| R8 | Fuga temporal inflando métricas | Media | Alto | Partición temporal, revisión obligatoria de variables, prueba intocada, revisión cruzada entre integrantes |
| R9 | Clasificación errónea de eventos (transferencias contadas como devolución, N5) | **Media** | **Alto** | Regla de tres vías (§6.2); conciliación A vs B; umbral de eventos `OTRO` < 2 % |
| R10 | Incidente de PII en el repositorio | Baja | Crítico | Hashing en ingesta, `.gitignore`, *hook* de pre-commit, datos fuera de Git |
| R11 | Snapshots faltantes rompen el *diff* | Media | Medio | Registro de cobertura (E3), marcado `imputado`, exclusión de la evaluación |
| R12 | El modelo no supera a Croston/naive | Media | Alto | Es un resultado válido y publicable si se documenta con rigor; reorientar el aporte hacia el análisis explicativo (SHAP) y el hallazgo del ciclo de devolución (E11) |
| R13 | Sin histórico de cupos, se pierde un predictor potente (P7) | Confirmado | Medio | Cupo como atributo estático; solicitar captura diaria desde hoy para trabajo futuro |

---

# 14. Acciones inmediatas — próximos 7 días

| # | Acción | Fecha |
|---|---|---|
| 1 | Enviar acta con P24–P29, destacando la contradicción de N12 y la recomendación de canal seguro de §5.8.1 | 15-sep |
| 2 | Inicializar repositorio con la estructura de §11, DVC y *pre-commit* | 15-sep |
| 3 | Escribir los 7 contratos de datos YAML | 16-sep |
| 4 | Implementar lectores con parsers explícitos para las **tres convenciones de fecha** y limpieza de `=""`, `?`, `"NULL"` | 17-sep |
| 5 | **Lote piloto de 7 días** de las 4 fuentes: medir tiempo de parseo y dimensionar el *backfill* | 17-sep |
| 5b | **Copia masiva del histórico de 24 meses** desde el equipo de logística, con verificación por hash — **máxima prioridad** (N14) | 15-sep |
| 5c | **Prueba empírica de N12:** tasa de coincidencia de `EQUIPMENT_ID` contra `Serie` e `IMSI`, y distribución de `APPROVED_QUANTITY` | 16-sep |
| 5d | Medir el tiempo entre `CREATED_WHEN` y el cierre para fijar *T* y truncar la ventana del target (N11) | 17-sep |
| 5e | Implementar la extracción automatizada desde el buzón (dentro de la ventana 06:00–23:59), con manifiesto y hash por adjunto | 17-sep |
| 6 | Implementar la regla de clasificación de §6.2 y tabular `MO_TYPE` × `TYPE_` × clase asignada, incluida la distribución de `MO_TYPE` **dentro** de las devoluciones | 18-sep |
| 6b | **Prueba de concepto de la extensión retrospectiva** (§5.6.1) sobre un mes del solapamiento: medir WMAPE de B contra A | 18-sep |
| 7 | Ejecutar E1–E3 del EDA sobre el lote piloto | 18-sep |
| 8 | Cerrar por escrito la ficha de definición del problema (§4) | 18-sep |
| 9 | Corregir en el documento capstone: cronograma Sep S3 (eliminar "clasificación") y precisión del criterio MAPE (§7.7) | 19-sep |
| 10 | **Punto de control:** lanzar *backfill* ola 1 y **decidir la vía de grano temporal** (A, B o C, §7.2.1) | 19-sep |

---

# 15. Referencias metodológicas

- Kreuzberger, D., Kühl, N., & Hirschl, S. (2023). Machine learning operations (MLOps): Overview, definition, and architecture. *IEEE Access, 11*, 31866–31879.
- Mehrabi, N., Morstatter, F., Saxena, N., Lerman, K., & Galstyan, A. (2021). A survey on bias and fairness in machine learning. *ACM Computing Surveys, 54*(6), 1–35.
- Studer, S., Bui, T. B., Drescher, C., Hanuschkin, A., Winkler, L., Peters, S., & Müller, K.-R. (2021). Towards CRISP-ML(Q): A machine learning process model with quality assurance methodology. *Machine Learning and Knowledge Extraction, 3*(2), 392–413.
- Syntetos, A. A., & Boylan, J. E. (2005). The accuracy of intermittent demand estimates. *International Journal of Forecasting, 21*(2), 303–314.
- Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and practice* (3.ª ed.). OTexts.
- Mapa metodológico "Fundamentos para Proyectos de IA" (XMind), incorporado a partir de la imagen proporcionada por el equipo.
