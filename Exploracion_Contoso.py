"""

Parte 1: Análisis preliminar de los datos (exploración de la estructura de cada tabla).

Para cada tabla se obtiene:
    - Número de filas y columnas
    - Tipo de dato de cada columna
    - Clasificación de cada columna (categórica, discreta o continua)
    - Cantidad de datos faltantes
    - Cantidad de valores distintos
    - Frecuencia relativa (probabilidad empírica) de los valores de las columnas
      categóricas o discretas con pocos valores distintos

Uso:
    1. Poner el Excel y el FactSales.txt en la misma carpeta que este script
       
    2. Ejecutar:  python Exploracion_Contoso.py
"""

import pandas as pd

# ----------------------------------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------------------------------
RUTA_EXCEL = "Contoso Sales.xlsx"
RUTA_FACTSALES = "FactSales.txt"

# Una columna con a lo sumo este número de valores distintos se considera
# apta para mostrar su tabla de frecuencias (probabilidades empíricas).
MAX_VALORES_FRECUENCIA = 15


# ----------------------------------------------------------------------------
# EXTRACCIÓN (Extract)
# ----------------------------------------------------------------------------
def cargar_excel(ruta):
    """Lee todas las hojas del Excel y devuelve un diccionario {nombre: DataFrame}."""
    # sheet_name=None le dice a pandas que lea todas las hojas del libro
    return pd.read_excel(ruta, sheet_name=None)


def numero_desde_texto(serie):
    """
    Convierte una columna de texto con formato numérico regional a float.
    En FactSales.txt los números vienen como '1 980' o '186,9 ':
        - espacio como separador de miles
        - coma como separador decimal
        - espacios sobrantes al final
    """
    limpia = (
        serie.str.replace(r"\s", "", regex=True)   # quita espacios (miles y sobrantes)
             .str.replace(",", ".", regex=False)   # coma decimal -> punto decimal
    )
    return pd.to_numeric(limpia)


def cargar_factsales(ruta):
    """Lee FactSales.txt (separado por tabuladores) y corrige los tipos de dato."""
    # Se lee todo como texto para controlar manualmente la conversión de cada columna
    df = pd.read_csv(ruta, sep="\t", dtype=str)
    df.columns = df.columns.str.strip()  # quita espacios sobrantes en los nombres

    # Columnas enteras (identificadores y cantidades)
    columnas_enteras = [
        "OrderID", "channelKey", "StoreKey", "ProductKey", "PromotionKey",
        "SalesQuantity", "ReturnQuantity", "Cantidad_total",
    ]
    for col in columnas_enteras:
        df[col] = pd.to_numeric(df[col])

    # Columnas decimales con formato regional (coma decimal y espacio de miles)
    df["Precio_unitario"] = numero_desde_texto(df["Precio_unitario"])
    df["Ingresos"] = numero_desde_texto(df["Ingresos"])

    # Fecha en formato día/mes/año
    df["DateKey"] = pd.to_datetime(df["DateKey"], format="%d/%m/%Y %H:%M:%S")

    # Columnas de texto: se les quitan los espacios sobrantes
    for col in ["Devolución", "Venta_type", "Devolución_type"]:
        df[col] = df[col].str.strip()

    return df


# ----------------------------------------------------------------------------
# TRANSFORMACIÓN (Transform): análisis preliminar
# ----------------------------------------------------------------------------
def clasificar_columna(serie):
    """
    Clasifica una columna según su tipo de dato:
        - Categórica: texto o etiquetas
        - Fecha: tipo datetime
        - Discreta: números enteros (conteos o identificadores)
        - Continua: números decimales
    Es una clasificación automática de partida; los identificadores (llaves)
    se deben interpretar a mano, pues son enteros pero no son variables numéricas.
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "Fecha"
    if pd.api.types.is_integer_dtype(serie):
        return "Discreta"
    if pd.api.types.is_float_dtype(serie):
        return "Continua"
    return "Categórica"


def resumen_estructura(nombre, df):
    """Imprime la estructura de una tabla y devuelve un DataFrame resumen por columna."""
    n_filas, n_columnas = df.shape
    print("=" * 78)
    print(f"TABLA: {nombre}   ({n_filas:,} filas x {n_columnas} columnas)")
    print("=" * 78)

    filas = []
    for col in df.columns:
        serie = df[col]
        filas.append({
            "Columna": col,
            "Tipo de dato": str(serie.dtype),
            "Clasificación": clasificar_columna(serie),
            "Faltantes": int(serie.isna().sum()),
            "Valores distintos": int(serie.nunique()),
        })
    resumen = pd.DataFrame(filas)
    print(resumen.to_string(index=False))
    print(f"\nFilas duplicadas completas: {int(df.duplicated().sum())}")
    return resumen


def frecuencias(nombre, df):
    """
    Imprime la frecuencia relativa (probabilidad empírica) de cada valor para las
    columnas con pocos valores distintos.
    P(X = x) = (veces que aparece x) / (total de filas)
    """
    for col in df.columns:
        serie = df[col]
        if 1 < serie.nunique() <= MAX_VALORES_FRECUENCIA:
            prob = serie.value_counts(normalize=True, dropna=False).sort_index()
            print(f"\n[{nombre}] Probabilidad empírica de '{col}':")
            print(prob.round(4).to_string())


def estadisticos_basicos(nombre, df):
    """Resumen descriptivo (mín, máx, media, cuartiles) de las columnas numéricas continuas."""
    continuas = [c for c in df.columns if clasificar_columna(df[c]) == "Continua"]
    if continuas:
        print(f"\n[{nombre}] Resumen descriptivo de columnas continuas:")
        print(df[continuas].describe().round(2).to_string())


def revisar_integridad(tablas, fact):
    """
    Verifica que las llaves de FactSales existan en sus tablas de dimensión.
    Esto sirve para el diseño de la base de datos relacional.
    """
    print("=" * 78)
    print("INTEGRIDAD REFERENCIAL: llaves de FactSales vs tablas de dimensión")
    print("=" * 78)
    relaciones = [
        ("channelKey", "DimChannel", "ChannelKey"),
        ("StoreKey", "DimStores", "StoreKey"),
        ("ProductKey", "DimProduct", "ProductKey"),
        ("PromotionKey", "DimPromotion", "PromotionKey"),
    ]
    for col_fact, tabla_dim, col_dim in relaciones:
        llaves_fact = set(fact[col_fact].unique())
        llaves_dim = set(tablas[tabla_dim][col_dim].unique())
        huerfanas = sorted(llaves_fact - llaves_dim)
        estado = "OK" if not huerfanas else f"FALTAN en la dimensión: {huerfanas[:10]}"
        print(f"FactSales.{col_fact} -> {tabla_dim}.{col_dim}: {estado}")

# ----------------------------------------------------------------------------
# ANÁLISIS ADICIONAL: GRANULARIDAD Y CALIDAD RELACIONAL
# ----------------------------------------------------------------------------

def analizar_granularidad(fact):
    """
    Determina si OrderID identifica un registro único y examina
    posibles repeticiones en las dimensiones de la tabla de hechos.
    """
    print("=" * 78)
    print("ANÁLISIS DE GRANULARIDAD: FactSales")
    print("=" * 78)

    total = len(fact)
    unicos = fact["OrderID"].nunique()
    repetidos = fact["OrderID"].duplicated().sum()

    print(f"Total de registros: {total:,}")
    print(f"OrderID distintos: {unicos:,}")
    print(f"OrderID repetidos: {repetidos:,}")
    print(f"¿OrderID es único?: {'SI' if repetidos == 0 else 'NO'}")

    if repetidos > 0:
        frecuencia = fact["OrderID"].value_counts()
        print("\nPedidos con mayor cantidad de registros:")
        print(frecuencia.head(10).to_string())

    # Comprobar combinaciones de pedido y producto
    columnas = ["OrderID", "ProductKey"]
    duplicados = fact.duplicated(subset=columnas).sum()

    print(f"\nCombinaciones OrderID-ProductKey repetidas: {duplicados:,}")

    # Comprobar combinaciones completas de dimensiones
    dimensiones = [
        "OrderID", "DateKey", "channelKey",
        "StoreKey", "ProductKey", "PromotionKey"
    ]

    duplicados_dim = fact.duplicated(subset=dimensiones).sum()

    print(
        "Combinaciones completas de pedido y dimensiones repetidas:",
        f"{duplicados_dim:,}"
    )


def revisar_integridad_completa(tablas, fact):
    """
    Verifica las siete relaciones entre las tablas de dimensiones
    y FactSales, incluyendo las relaciones internas.
    """
    print("=" * 78)
    print("ANÁLISIS DE INTEGRIDAD REFERENCIAL COMPLETA")
    print("=" * 78)

    relaciones = [
        ("FactSales", "channelKey", "DimChannel", "ChannelKey"),
        ("FactSales", "StoreKey", "DimStores", "StoreKey"),
        ("FactSales", "ProductKey", "DimProduct", "ProductKey"),
        ("FactSales", "PromotionKey", "DimPromotion", "PromotionKey"),
        ("DimStores", "GeographyKey", "DimGeography", "GeographyKey"),
        ("DimProduct", "ProductSubcategoryKey",
         "DimProductSubCategory", "ProductSubcategoryKey"),
        ("DimProductSubCategory", "ProductCategoryKey",
         "DimProductCategory", "ProductCategoryKey"),
    ]

    for origen, col_origen, destino, col_destino in relaciones:

        df_origen = fact if origen == "FactSales" else tablas[origen]
        df_destino = tablas[destino]

        llaves_origen = set(df_origen[col_origen].dropna().unique())
        llaves_destino = set(df_destino[col_destino].dropna().unique())

        huerfanas = llaves_origen - llaves_destino

        estado = "OK" if not huerfanas else f"ERROR: {len(huerfanas)}"

        print(
            f"{origen}.{col_origen} -> "
            f"{destino}.{col_destino}: {estado}"
        )

        if huerfanas:
            print("  Ejemplos:", list(huerfanas)[:10])


def revisar_consistencia(fact):
    """
    Examina posibles inconsistencias entre cantidades,
    devoluciones, precios e ingresos.
    """
    print("=" * 78)
    print("ANÁLISIS DE CONSISTENCIA DE FactSales")
    print("=" * 78)

    # Valores negativos o cero en cantidades
    for col in ["SalesQuantity", "ReturnQuantity", "Cantidad_total"]:
        negativos = (fact[col] < 0).sum()
        ceros = (fact[col] == 0).sum()

        print(f"\n{col}:")
        print(f"  Valores negativos: {negativos:,}")
        print(f"  Valores iguales a cero: {ceros:,}")

    # Consistencia entre devolución y cantidad devuelta
    devolucion_incoherente = (
        ((fact["ReturnQuantity"] > 0) & (fact["Devolución"] != "SI")) |
        ((fact["ReturnQuantity"] == 0) & (fact["Devolución"] != "NO"))
    ).sum()

    print(
        "\nInconsistencias Devolución vs ReturnQuantity:",
        f"{devolucion_incoherente:,}"
    )

    # Clasificación de devoluciones
    print("\nRelación entre devolución y tipo:")
    print(
        pd.crosstab(
            fact["Devolución"],
            fact["Devolución_type"]
        ).to_string()
    )

    # Revisar si los ingresos corresponden a precio por cantidad
    ingresos_calculados = (
        fact["Precio_unitario"] * fact["Cantidad_total"]
    )

    diferencias = (
        fact["Ingresos"] - ingresos_calculados
    ).abs()

    print("\nIngresos vs Precio_unitario * Cantidad_total:")
    print(f"  Diferencias mayores a 0.01: {(diferencias > 0.01).sum():,}")
    print(f"  Diferencia máxima: {diferencias.max():.4f}")


# ----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------------
def main():
    # 1) Extracción
    tablas = cargar_excel(RUTA_EXCEL)
    tablas["FactSales"] = cargar_factsales(RUTA_FACTSALES)

    # 2) Análisis preliminar de cada tabla
    for nombre, df in tablas.items():
        resumen_estructura(nombre, df)
        estadisticos_basicos(nombre, df)
        frecuencias(nombre, df)
        print()

    # 3) Revisión de llaves para el diseño relacional
    revisar_integridad(tablas, tablas["FactSales"])

    # 4) Rango de fechas de FactSales
    fechas = tablas["FactSales"]["DateKey"]
    print(f"\nRango de fechas de FactSales: {fechas.min().date()} a {fechas.max().date()}")

    # 5) Análisis de granularidad
    analizar_granularidad(tablas["FactSales"])

    # 6) Integridad referencial completa
    revisar_integridad_completa(tablas, tablas["FactSales"])

    # 7) Consistencia de los datos
    revisar_consistencia(tablas["FactSales"])



if __name__ == "__main__":
    main()





