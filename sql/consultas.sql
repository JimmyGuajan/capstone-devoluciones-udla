/* ============================================================
   DW_DEVOLUCIONES — consultas de exploración
   Servidor: (localdb)\MSSQLLocalDB
   ============================================================ */

USE DW_DEVOLUCIONES;
GO

/* ---------- Qué hay cargado ---------- */
SELECT s.name AS esquema, t.name AS tabla,
       SUM(p.rows) AS filas
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
GROUP BY s.name, t.name
ORDER BY filas DESC;


/* ============================================================
   1 · LA VARIABLE OBJETIVO
   ============================================================ */

/* Todas las devoluciones, con distribuidor, zona y valor en dólares */
SELECT * FROM mart.vw_devoluciones ORDER BY valor_usd DESC;

/* Resumen por distribuidor */
SELECT ruc, distribuidor, provincia,
       COUNT(*)          AS lineas,
       SUM(unidades)     AS unidades,
       SUM(valor_usd)    AS valor_usd
FROM mart.vw_devoluciones
GROUP BY ruc, distribuidor, provincia
ORDER BY unidades DESC;

/* Devolución contra pedido: la tasa que el proyecto quiere predecir */
SELECT p.ruc, p.distribuidor, p.segmento,
       SUM(p.unidades)                       AS pedidas,
       ISNULL(d.unidades, 0)                 AS devueltas,
       CAST(ISNULL(d.unidades,0) AS FLOAT)
            / NULLIF(SUM(p.unidades), 0)     AS tasa
FROM mart.vw_pedidos p
LEFT JOIN (SELECT ruc, segmento, SUM(unidades) AS unidades
           FROM mart.vw_devoluciones GROUP BY ruc, segmento) d
       ON d.ruc = p.ruc AND d.segmento = p.segmento
GROUP BY p.ruc, p.distribuidor, p.segmento, d.unidades
ORDER BY tasa DESC;


/* ============================================================
   2 · POR QUÉ LA REGLA NO PUEDE USAR MO_TYPE
   El 100 % de las devoluciones lleva la etiqueta que el catálogo
   del cliente invita a excluir.
   ============================================================ */
SELECT clase, mo_tipo, COUNT(*) AS lineas, SUM(cantidad) AS unidades
FROM fact.eventos
GROUP BY clase, mo_tipo
ORDER BY clase, lineas DESC;


/* ============================================================
   3 · CALIDAD DEL CATÁLOGO DE BODEGAS
   Lo que se pierde por las 66 bodegas que faltan.
   ============================================================ */
SELECT * FROM mart.vw_calidad_catalogo ORDER BY unidades DESC;

/* Cuánto volumen queda sin poder atribuirse a un distribuidor */
SELECT CASE WHEN b.bodega_id IS NULL THEN 'SIN CATALOGO' ELSE 'catalogada' END AS estado,
       COUNT(*) AS lineas, SUM(o.cantidad) AS unidades
FROM fact.ordenes o
LEFT JOIN dim.bodega b ON b.bodega_id = o.bodega_destino
WHERE o.bodega_origen = 'PK'
GROUP BY CASE WHEN b.bodega_id IS NULL THEN 'SIN CATALOGO' ELSE 'catalogada' END;


/* ============================================================
   4 · CENSURA A LA DERECHA
   El 98 % de las devoluciones no se ha consumado.
   ============================================================ */
SELECT mo_estado, COUNT(*) AS lineas, SUM(cantidad) AS unidades,
       CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS DECIMAL(5,1)) AS pct
FROM fact.eventos
WHERE clase = 'DEVOLUCION'
GROUP BY mo_estado;


/* ============================================================
   5 · SELL-OUT: LA SERIE LARGA (20 MESES)
   ============================================================ */
SELECT mes, SUM(sellout) AS unidades, SUM(valor) AS valor_usd
FROM fact.sellout_mensual
GROUP BY mes ORDER BY mes;

/* Estacionalidad: sell-out medio por mes calendario */
SELECT MONTH(mes) AS mes_num,
       SUM(sellout) / COUNT(DISTINCT mes) AS sellout_medio
FROM fact.sellout_mensual
GROUP BY MONTH(mes) ORDER BY mes_num;

/* Los cinco distribuidores con más rotación */
SELECT TOP 5 s.ruc, d.distribuidor, SUM(s.sellout) AS unidades
FROM fact.sellout_mensual s
LEFT JOIN dim.distribuidor d ON d.ruc = s.ruc
GROUP BY s.ruc, d.distribuidor ORDER BY unidades DESC;


/* ============================================================
   6 · VENTA AL PARTNER NO ES SELL-IN A DISTRIBUIDORES
   Las marcas MVNO concentran la entrada y casi no registran salida.
   ============================================================ */
SELECT producto,
       SUM(CASE WHEN flujo = 'SELL_IN'  THEN 1 ELSE 0 END) AS sell_in,
       SUM(CASE WHEN flujo = 'SELL_OUT' THEN 1 ELSE 0 END) AS sell_out,
       CAST(1.0 * SUM(CASE WHEN flujo='SELL_OUT' THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN flujo='SELL_IN' THEN 1 ELSE 0 END),0)
            AS DECIMAL(10,4)) AS ratio_out_in
FROM fact.ventas
GROUP BY producto
HAVING SUM(CASE WHEN flujo = 'SELL_IN' THEN 1 ELSE 0 END) > 1000
ORDER BY sell_in DESC;


/* ============================================================
   7 · INVENTARIO Y OBSOLESCENCIA
   El KPI del capstone: 5,9 % actual contra meta de 2,9 %.
   ============================================================ */
SELECT fecha,
       COUNT(*) AS unidades,
       SUM(CASE WHEN condicion = 'Obsoleto' THEN 1 ELSE 0 END) AS obsoletas,
       CAST(100.0 * SUM(CASE WHEN condicion='Obsoleto' THEN 1 ELSE 0 END)
            / COUNT(*) AS DECIMAL(5,2)) AS pct_obsoleto,
       SUM(precio) AS valor_usd
FROM fact.stock_equipos
GROUP BY fecha ORDER BY fecha;

/* Obsolescencia por bodega — dónde se concentra el riesgo */
SELECT TOP 20 e.bodega_nombre, b.provincia,
       COUNT(*) AS unidades,
       SUM(CASE WHEN e.condicion='Obsoleto' THEN 1 ELSE 0 END) AS obsoletas,
       SUM(CASE WHEN e.condicion='Obsoleto' THEN e.precio ELSE 0 END) AS valor_en_riesgo
FROM fact.stock_equipos e
LEFT JOIN dim.bodega b ON b.bodega_id = e.bodega_id
WHERE e.fecha = (SELECT MAX(fecha) FROM fact.stock_equipos)
GROUP BY e.bodega_nombre, b.provincia
HAVING SUM(CASE WHEN e.condicion='Obsoleto' THEN 1 ELSE 0 END) > 0
ORDER BY valor_en_riesgo DESC;


/* ============================================================
   8 · LA SÁBANA DE MODELADO
   ============================================================ */
SELECT * FROM mart.vw_resumen_distribuidor ORDER BY unidades_devueltas DESC;

/* Densidad del target: por qué el modelo todavía no entrena */
SELECT COUNT(*) AS celdas,
       SUM(CASE WHEN dev_u > 0 THEN 1 ELSE 0 END) AS con_devolucion,
       CAST(100.0 * SUM(CASE WHEN dev_u > 0 THEN 1 ELSE 0 END)
            / COUNT(*) AS DECIMAL(5,2)) AS densidad_pct
FROM mart.panel;

/* Demanda neta calculada por el modelo */
SELECT * FROM mart.demanda_neta WHERE ped_u > 0 ORDER BY ped_u DESC;
