/* ============================================================================
   ANTIGÜEDAD DE INVENTARIO — reproduce el reporte del negocio
   Base: DW_DEVOLUCIONES_HIST   ·   Servidor: (localdb)\MSSQLLocalDB

   La tabla base es fact.estadias: un registro por (imei, bodega, desde, hasta).
   De 13,8 M de filas de inventario diario quedan 763 mil tramos.

   DOS AJUSTES QUE HAY QUE CONOCER
   -------------------------------
   @lag = 2   El inventario se toma a las 06:00, así que una unidad movida el
              día X recién aparece el día X+2. Verificado: 207 de 238 equipos
              de un listado del negocio tienen exactamente ese desfase.
              Sin este ajuste la antigüedad queda 2 días corta.

   @corte     La tabla llega hasta MAX(hasta). Si el reporte del negocio se
              generó después, hay que sumar esa diferencia a los días.
   ============================================================================ */

USE DW_DEVOLUCIONES_HIST;
GO

/* ---------------------------------------------------------------------------
   1 · EL REPORTE: unidades con 60+ días a una fecha
   Reproduce el formato de Revision.xlsx
   --------------------------------------------------------------------------- */
DECLARE @corte  DATE = (SELECT MAX(hasta) FROM fact.estadias);
DECLARE @umbral INT  = 60;
DECLARE @lag    INT  = 2;

SELECT e.imei,
       e.sku                                              AS codigo_articulo,
       e.modelo,
       e.bodega_nombre                                    AS bodega,
       e.bodega_id,
       e.condicion,
       e.precio,
       DATEADD(DAY, -@lag, e.desde)                       AS fecha_ingreso,
       @corte                                             AS fecha_corte,
       DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte)  AS dias
FROM   fact.estadias e
WHERE  e.desde <= @corte
  AND  e.hasta >= @corte                       -- sigue en esa bodega al corte
  AND  DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) >= @umbral
ORDER  BY dias DESC;
GO


/* ---------------------------------------------------------------------------
   2 · POR BODEGA — dónde se concentra el inventario detenido
   --------------------------------------------------------------------------- */
DECLARE @corte DATE = (SELECT MAX(hasta) FROM fact.estadias);
DECLARE @umbral INT = 60, @lag INT = 2;

SELECT e.bodega_nombre                              AS bodega,
       COUNT(*)                                     AS unidades,
       CAST(SUM(e.precio) AS DECIMAL(14,2))         AS valor_usd,
       CAST(AVG(CAST(DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) AS FLOAT))
            AS DECIMAL(6,1))                        AS dias_promedio
FROM   fact.estadias e
WHERE  e.desde <= @corte AND e.hasta >= @corte
  AND  DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) >= @umbral
GROUP  BY e.bodega_nombre
ORDER  BY valor_usd DESC;
GO


/* ---------------------------------------------------------------------------
   3 · LOS TRES ALCANCES
   Cada archivo que entregó el negocio usa un alcance distinto de bodegas.
   Esta consulta los separa para poder comparar con el que corresponda.
   --------------------------------------------------------------------------- */
DECLARE @corte DATE = (SELECT MAX(hasta) FROM fact.estadias);
DECLARE @umbral INT = 60, @lag INT = 2;

SELECT CASE
         WHEN e.en_central = 1                       THEN '1 · bodegas centrales'
         WHEN e.bodega_nombre LIKE 'CAVS %'
              AND e.bodega_nombre NOT LIKE '%AE%'    THEN '2 · tiendas propias (CAVS)'
         WHEN e.bodega_nombre LIKE 'TIENDA VIRTUAL%'
           OR e.bodega_nombre LIKE 'REF. OPERACIONES%'
           OR e.bodega_nombre LIKE 'PRUEBAS%'        THEN '3 · operación interna'
         ELSE                                             '4 · canal externo'
       END                                           AS alcance,
       COUNT(*)                                      AS unidades,
       CAST(SUM(e.precio) AS DECIMAL(14,2))          AS valor_usd
FROM   fact.estadias e
WHERE  e.desde <= @corte AND e.hasta >= @corte
  AND  DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) >= @umbral
GROUP  BY CASE
         WHEN e.en_central = 1                       THEN '1 · bodegas centrales'
         WHEN e.bodega_nombre LIKE 'CAVS %'
              AND e.bodega_nombre NOT LIKE '%AE%'    THEN '2 · tiendas propias (CAVS)'
         WHEN e.bodega_nombre LIKE 'TIENDA VIRTUAL%'
           OR e.bodega_nombre LIKE 'REF. OPERACIONES%'
           OR e.bodega_nombre LIKE 'PRUEBAS%'        THEN '3 · operación interna'
         ELSE                                             '4 · canal externo'
       END
ORDER  BY alcance;
GO


/* ---------------------------------------------------------------------------
   4 · POR MARCA — la vista que usa el modelo
   --------------------------------------------------------------------------- */
DECLARE @corte DATE = (SELECT MAX(hasta) FROM fact.estadias);
DECLARE @umbral INT = 60, @lag INT = 2;

SELECT e.marca,
       COUNT(*)                                     AS con_60_mas_dias,
       CAST(SUM(e.precio) AS DECIMAL(14,2))         AS valor_usd,
       CAST(AVG(CAST(DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) AS FLOAT))
            AS DECIMAL(6,1))                        AS dias_promedio
FROM   fact.estadias e
WHERE  e.desde <= @corte AND e.hasta >= @corte
  AND  DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), @corte) >= @umbral
  AND  e.en_central = 0
GROUP  BY e.marca
ORDER  BY con_60_mas_dias DESC;
GO


/* ---------------------------------------------------------------------------
   5 · SERIE MENSUAL — cuántas unidades cumplen el umbral cada mes
   Es el flujo que alimenta el modelo, no la foto.
   --------------------------------------------------------------------------- */
DECLARE @umbral INT = 60, @lag INT = 2;
DECLARE @tope DATE = (SELECT MAX(hasta) FROM fact.estadias);

WITH cumplen AS (
  SELECT e.marca,
         DATEADD(DAY, @umbral - @lag, e.desde) AS fecha_cumple,
         e.precio
  FROM   fact.estadias e
  WHERE  e.en_central = 0
    AND  DATEDIFF(DAY, DATEADD(DAY,-@lag,e.desde), e.hasta) >= @umbral
)
SELECT DATEFROMPARTS(YEAR(fecha_cumple), MONTH(fecha_cumple), 1) AS mes,
       COUNT(*)                             AS unidades,
       CAST(SUM(precio) AS DECIMAL(14,2))   AS valor_usd
FROM   cumplen
WHERE  fecha_cumple <= @tope
GROUP  BY DATEFROMPARTS(YEAR(fecha_cumple), MONTH(fecha_cumple), 1)
ORDER  BY mes;
GO


/* ---------------------------------------------------------------------------
   6 · VALIDAR CONTRA UN LISTADO DEL NEGOCIO
   Pega los IMEI del archivo en la tabla temporal y compara.
   --------------------------------------------------------------------------- */
DROP TABLE IF EXISTS #listado;
CREATE TABLE #listado (imei VARCHAR(20), bodega VARCHAR(120), fecha_negocio DATE);

-- Incluir la bodega es importante: sin ella la consulta también devuelve el
-- tramo que la unidad pasó en bodega central antes de llegar al local.
INSERT INTO #listado (imei, bodega, fecha_negocio) VALUES
  ('350135179665922', 'CAVS SAN MARINO',   '2026-01-12'),
  ('356935404937721', 'CAVS SAN MARINO',   '2026-01-12'),
  ('354373472168635', 'CAVS MALL DEL RIO', '2026-01-16');
  -- pegar aquí el resto del archivo

SELECT l.imei,
       l.bodega,
       l.fecha_negocio,
       DATEADD(DAY,-2,e.desde)                                  AS fecha_nuestra,
       DATEDIFF(DAY, l.fecha_negocio, DATEADD(DAY,-2,e.desde))  AS diferencia_dias,
       e.desde, e.hasta,
       CASE WHEN e.imei IS NULL THEN 'no cruza'
            WHEN ABS(DATEDIFF(DAY, l.fecha_negocio, DATEADD(DAY,-2,e.desde))) <= 2
                 THEN 'coincide'
            ELSE 'revisar' END                                  AS estado
FROM   #listado l
LEFT   JOIN fact.estadias e
       ON  e.imei = l.imei
      AND  e.bodega_nombre = l.bodega
      AND  e.hasta >= l.fecha_negocio
ORDER  BY ABS(DATEDIFF(DAY, l.fecha_negocio, DATEADD(DAY,-2,e.desde))) DESC;
GO


/* ---------------------------------------------------------------------------
   7 · EL RECORRIDO COMPLETO DE UNA UNIDAD
   Útil para explicar un caso concreto: dónde estuvo y cuánto.
   --------------------------------------------------------------------------- */
SELECT e.desde, e.hasta, e.dias_tramo,
       e.bodega_nombre, e.en_central, e.condicion, e.modelo
FROM   fact.estadias e
WHERE  e.imei = '352824580580287'
ORDER  BY e.desde;
GO


/* ---------------------------------------------------------------------------
   8 · CALIDAD: días sin snapshot
   Un tramo cuyo inicio cae justo después de un hueco tiene la antigüedad
   subestimada. dias_tramo cuenta días de calendario, dias_observados cuenta
   días con inventario: la diferencia son los días sin dato.
   --------------------------------------------------------------------------- */
SELECT CASE WHEN dias_tramo - dias_observados = 0 THEN 'sin huecos'
            WHEN dias_tramo - dias_observados <= 2 THEN 'hueco de 1-2 días'
            ELSE 'hueco de 3+ días (antigüedad dudosa)' END AS calidad,
       COUNT(*)                                             AS tramos,
       CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS DECIMAL(5,1)) AS pct
FROM   fact.estadias
GROUP  BY CASE WHEN dias_tramo - dias_observados = 0 THEN 'sin huecos'
               WHEN dias_tramo - dias_observados <= 2 THEN 'hueco de 1-2 días'
               ELSE 'hueco de 3+ días (antigüedad dudosa)' END
ORDER  BY tramos DESC;
GO
