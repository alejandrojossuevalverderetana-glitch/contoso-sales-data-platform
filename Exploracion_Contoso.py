"""
Proyecto 01 - Principios de Análisis de Datos (Contoso Sales)
Modelos Probabilísticos de Señales y Sistemas - II-2026

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


if __name__ == "__main__":
    main()
