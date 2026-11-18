
-- ============================================================
-- Proyecto: Contoso Sales
-- Archivo: 04_validate_database.sql
--
-- Descripcion:
-- Validacion de integridad y consistencia de la base de datos.
--
-- Este script no modifica los datos.
-- ============================================================


-- ============================================================
-- 1. VERIFICACION DE CANTIDAD DE REGISTROS
-- ============================================================

SELECT
    tabla,
    registros,
    registros_esperados,
    CASE
        WHEN registros = registros_esperados THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM (
    SELECT 'DimChannel' AS tabla,
           COUNT(*) AS registros,
           4 AS registros_esperados
    FROM "DimChannel"

    UNION ALL

    SELECT 'DimDate', COUNT(*), 1096
    FROM "DimDate"

    UNION ALL

    SELECT 'DimGeography', COUNT(*), 674
    FROM "DimGeography"

    UNION ALL

    SELECT 'DimStores', COUNT(*), 310
    FROM "DimStores"

    UNION ALL

    SELECT 'DimProductCategory', COUNT(*), 8
    FROM "DimProductCategory"

    UNION ALL

    SELECT 'DimProductSubCategory', COUNT(*), 44
    FROM "DimProductSubCategory"

    UNION ALL

    SELECT 'DimProduct', COUNT(*), 1690
    FROM "DimProduct"

    UNION ALL

    SELECT 'DimPromotion', COUNT(*), 28
    FROM "DimPromotion"

    UNION ALL

    SELECT 'FactSales', COUNT(*), 2282482
    FROM "FactSales"
) AS conteos
ORDER BY tabla;


-- ============================================================
-- 2. VERIFICACION DE GRANULARIDAD DE FACTSALES
-- ============================================================

SELECT
    COUNT(*) AS total_registros,
    COUNT(DISTINCT "OrderID") AS orderid_distintos,
    COUNT(*) - COUNT(DISTINCT "OrderID") AS orderid_duplicados,
    CASE
        WHEN COUNT(*) = COUNT(DISTINCT "OrderID")
        THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM "FactSales";


-- ============================================================
-- 3. VERIFICACION DEL RANGO DE FECHAS
-- ============================================================

SELECT
    MIN("DateKey") AS fecha_minima,
    MAX("DateKey") AS fecha_maxima,
    COUNT(DISTINCT "DateKey") AS fechas_distintas,
    CASE
        WHEN MIN("DateKey") = DATE '2007-01-01'
         AND MAX("DateKey") = DATE '2009-12-31'
         AND COUNT(DISTINCT "DateKey") = 1096
        THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM "FactSales";


-- ============================================================
-- 4. INTEGRIDAD REFERENCIAL
-- ============================================================

SELECT
    relacion,
    referencias_invalidas,
    CASE
        WHEN referencias_invalidas = 0 THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM (
    SELECT
        'FactSales -> DimDate' AS relacion,
        COUNT(*) AS referencias_invalidas
    FROM "FactSales" f
    LEFT JOIN "DimDate" d
        ON f."DateKey" = d."DateKey"
    WHERE d."DateKey" IS NULL

    UNION ALL

    SELECT
        'FactSales -> DimChannel',
        COUNT(*)
    FROM "FactSales" f
    LEFT JOIN "DimChannel" d
        ON f."channelKey" = d."ChannelKey"
    WHERE d."ChannelKey" IS NULL

    UNION ALL

    SELECT
        'FactSales -> DimStores',
        COUNT(*)
    FROM "FactSales" f
    LEFT JOIN "DimStores" d
        ON f."StoreKey" = d."StoreKey"
    WHERE d."StoreKey" IS NULL

    UNION ALL

    SELECT
        'FactSales -> DimProduct',
        COUNT(*)
    FROM "FactSales" f
    LEFT JOIN "DimProduct" d
        ON f."ProductKey" = d."ProductKey"
    WHERE d."ProductKey" IS NULL

    UNION ALL

    SELECT
        'FactSales -> DimPromotion',
        COUNT(*)
    FROM "FactSales" f
    LEFT JOIN "DimPromotion" d
        ON f."PromotionKey" = d."PromotionKey"
    WHERE d."PromotionKey" IS NULL

    UNION ALL

    SELECT
        'DimStores -> DimGeography',
        COUNT(*)
    FROM "DimStores" s
    LEFT JOIN "DimGeography" g
        ON s."GeographyKey" = g."GeographyKey"
    WHERE g."GeographyKey" IS NULL

    UNION ALL

    SELECT
        'DimProduct -> DimProductSubCategory',
        COUNT(*)
    FROM "DimProduct" p
    LEFT JOIN "DimProductSubCategory" s
        ON p."ProductSubcategoryKey" = s."ProductSubcategoryKey"
    WHERE s."ProductSubcategoryKey" IS NULL

    UNION ALL

    SELECT
        'DimProductSubCategory -> DimProductCategory',
        COUNT(*)
    FROM "DimProductSubCategory" s
    LEFT JOIN "DimProductCategory" c
        ON s."ProductCategoryKey" = c."ProductCategoryKey"
    WHERE c."ProductCategoryKey" IS NULL
) AS relaciones
ORDER BY relacion;


-- ============================================================
-- 5. VERIFICACION DE RESTRICCIONES
-- ============================================================

SELECT
    conrelid::regclass AS tabla,
    conname AS restriccion,
    CASE contype
        WHEN 'p' THEN 'PRIMARY KEY'
        WHEN 'f' THEN 'FOREIGN KEY'
    END AS tipo,
    convalidated AS validada,
    CASE
        WHEN convalidated THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND contype IN ('p', 'f')
ORDER BY tabla, tipo, restriccion;


-- ============================================================
-- 6. CONSISTENCIA DE INGRESOS
-- ============================================================

SELECT
    COUNT(*) AS total_registros,
    COUNT(*) FILTER (
        WHERE ABS(
            "Ingresos" -
            ("Precio_unitario" * "Cantidad_total")
        ) > 0.01
    ) AS inconsistencias,
    MAX(
        ABS(
            "Ingresos" -
            ("Precio_unitario" * "Cantidad_total")
        )
    ) AS diferencia_maxima,
    CASE
        WHEN COUNT(*) FILTER (
            WHERE ABS(
                "Ingresos" -
                ("Precio_unitario" * "Cantidad_total")
            ) > 0.01
        ) = 0
        THEN 'OK'
        ELSE 'REVISAR'
    END AS resultado
FROM "FactSales";


-- ============================================================
-- 7. CONSISTENCIA DE CANTIDADES Y DEVOLUCIONES
-- ============================================================

SELECT
    COUNT(*) FILTER (
        WHERE "SalesQuantity" < 0
    ) AS ventas_negativas,

    COUNT(*) FILTER (
        WHERE "ReturnQuantity" < 0
    ) AS devoluciones_negativas,

    COUNT(*) FILTER (
        WHERE "Cantidad_total" < 0
    ) AS cantidades_net_as_negativas,

    COUNT(*) FILTER (
        WHERE
            ("ReturnQuantity" = 0 AND "Devolución" IS DISTINCT FROM 'NO')
            OR
            ("ReturnQuantity" > 0 AND "Devolución" IS DISTINCT FROM 'SI')
    ) AS inconsistencias_devolucion

FROM "FactSales";


-- ============================================================
-- FIN DE LAS VALIDACIONES
-- ============================================================
