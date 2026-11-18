
-- ============================================================
-- Proyecto: Contoso Sales
-- Archivo: 01_create_schema.sql
-- Descripción: Creación de las tablas y relaciones
-- ============================================================

-- ------------------------------------------------------------
-- 1. Dimensiones principales
-- ------------------------------------------------------------

CREATE TABLE "DimChannel" (
    "ChannelKey" INTEGER PRIMARY KEY,
    "ChannelName" VARCHAR(100) NOT NULL
);

CREATE TABLE "DimGeography" (
    "GeographyKey" INTEGER PRIMARY KEY,
    "ContinentName" VARCHAR(100),
    "RegionCountryName" VARCHAR(150)
);

CREATE TABLE "DimStores" (
    "StoreKey" INTEGER PRIMARY KEY,
    "GeographyKey" INTEGER,
    "StoreType" VARCHAR(100),
    "StoreName" VARCHAR(150),
    "EmployeeCount" INTEGER,
    "SellingAreaSize" INTEGER,

    CONSTRAINT fk_stores_geography
        FOREIGN KEY ("GeographyKey")
        REFERENCES "DimGeography" ("GeographyKey")
);

CREATE TABLE "DimProductCategory" (
    "ProductCategoryKey" INTEGER PRIMARY KEY,
    "ProductCategory" VARCHAR(150) NOT NULL
);

CREATE TABLE "DimProductSubCategory" (
    "ProductSubcategoryKey" INTEGER PRIMARY KEY,
    "ProductSubcategoryName" VARCHAR(150),
    "ProductCategoryKey" INTEGER,

    CONSTRAINT fk_subcategory_category
        FOREIGN KEY ("ProductCategoryKey")
        REFERENCES "DimProductCategory" ("ProductCategoryKey")
);

CREATE TABLE "DimProduct" (
    "ProductKey" INTEGER PRIMARY KEY,
    "ProductName" VARCHAR(250) NOT NULL,
    "ProductDescription" TEXT,
    "ProductSubcategoryKey" INTEGER,
    "Manufacturer" VARCHAR(150),
    "BrandName" VARCHAR(150),
    "ClassID" INTEGER,
    "ClassName" VARCHAR(100),
    "ColorID" INTEGER,
    "ColorName" VARCHAR(100),
    "Size" VARCHAR(100),
    "Weight" NUMERIC(12, 3),
    "UnitCost" NUMERIC(12, 2),
    "UnitPrice" NUMERIC(12, 2),

    CONSTRAINT fk_product_subcategory
        FOREIGN KEY ("ProductSubcategoryKey")
        REFERENCES "DimProductSubCategory" ("ProductSubcategoryKey")
);

CREATE TABLE "DimPromotion" (
    "PromotionKey" INTEGER PRIMARY KEY,
    "PromotionLabel" VARCHAR(150),
    "PromotionName" VARCHAR(150),
    "DiscountPercent" NUMERIC(5, 4),
    "StartDate" DATE,
    "EndDate" DATE,
    "Promo_days" INTEGER
);

-- ------------------------------------------------------------
-- 2. Dimensión temporal
-- ------------------------------------------------------------

CREATE TABLE "DimDate" (
    "DateKey" DATE PRIMARY KEY,
    "Year" INTEGER NOT NULL,
    "Quarter" INTEGER NOT NULL,
    "Month" INTEGER NOT NULL,
    "Day" INTEGER NOT NULL
);

-- Generación del calendario 2007-2009
INSERT INTO "DimDate" (
    "DateKey",
    "Year",
    "Quarter",
    "Month",
    "Day"
)
SELECT
    fecha::DATE,
    EXTRACT(YEAR FROM fecha)::INTEGER,
    EXTRACT(QUARTER FROM fecha)::INTEGER,
    EXTRACT(MONTH FROM fecha)::INTEGER,
    EXTRACT(DAY FROM fecha)::INTEGER
FROM GENERATE_SERIES(
    DATE '2007-01-01',
    DATE '2009-12-31',
    INTERVAL '1 day'
) AS fecha;

-- ------------------------------------------------------------
-- 3. Tabla de hechos
-- ------------------------------------------------------------

CREATE TABLE "FactSales" (
    "OrderID" BIGINT PRIMARY KEY,
    "DateKey" DATE NOT NULL,
    "channelKey" INTEGER NOT NULL,
    "StoreKey" INTEGER NOT NULL,
    "ProductKey" INTEGER NOT NULL,
    "PromotionKey" INTEGER NOT NULL,

    "SalesQuantity" INTEGER NOT NULL,
    "ReturnQuantity" INTEGER NOT NULL,
    "Cantidad_total" INTEGER NOT NULL,

    "Devolución" VARCHAR(10),
    "Venta_type" VARCHAR(50),
    "Devolución_type" VARCHAR(100),

    "Precio_unitario" NUMERIC(12, 2),
    "Ingresos" NUMERIC(14, 2),

    CONSTRAINT fk_sales_date
        FOREIGN KEY ("DateKey")
        REFERENCES "DimDate" ("DateKey"),

    CONSTRAINT fk_sales_channel
        FOREIGN KEY ("channelKey")
        REFERENCES "DimChannel" ("ChannelKey"),

    CONSTRAINT fk_sales_store
        FOREIGN KEY ("StoreKey")
        REFERENCES "DimStores" ("StoreKey"),

    CONSTRAINT fk_sales_product
        FOREIGN KEY ("ProductKey")
        REFERENCES "DimProduct" ("ProductKey"),

    CONSTRAINT fk_sales_promotion
        FOREIGN KEY ("PromotionKey")
        REFERENCES "DimPromotion" ("PromotionKey")
);

-- ============================================================
-- Fin del script
-- ============================================================
