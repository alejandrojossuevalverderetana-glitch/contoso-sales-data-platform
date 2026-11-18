
"""
Proyecto: Contoso Sales
Archivo: 02_load_dimensions.py

Descripción:
Carga las tablas de dimensiones desde el archivo Excel
hacia la base de datos PostgreSQL contoso_sales.
"""

from pathlib import Path
from getpass import getpass

import pandas as pd
from sqlalchemy import create_engine, URL, text


# ============================================================
# 1. CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

RUTA_EXCEL = BASE_DIR / "Contoso Sales.xlsx"

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "contoso_sales",
    "username": "postgres"
}

# Orden de carga según las dependencias entre dimensiones.
TABLAS_DIMENSIONES = [
    "DimChannel",
    "DimGeography",
    "DimProductCategory",
    "DimProductSubCategory",
    "DimStores",
    "DimProduct",
    "DimPromotion"
]


# ============================================================
# 2. CONEXIÓN A POSTGRESQL
# ============================================================

def crear_conexion():
    """Crea la conexión con PostgreSQL."""

    password = getpass("Contraseña de PostgreSQL: ")

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_CONFIG["username"],
        password=password,
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"]
    )

    engine = create_engine(url)

    return engine


# ============================================================
# 3. VALIDACIÓN DEL ARCHIVO EXCEL
# ============================================================

def validar_archivo():
    """Comprueba que el archivo Excel exista."""

    if not RUTA_EXCEL.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {RUTA_EXCEL}"
        )

    print(f"Archivo encontrado: {RUTA_EXCEL.name}")


# ============================================================
# 4. CARGA DE DIMENSIONES
# ============================================================

def cargar_dimensiones(engine):
    """Carga las dimensiones en PostgreSQL."""

    excel = pd.ExcelFile(RUTA_EXCEL)

    hojas_disponibles = excel.sheet_names

    # Comprobar que todas las hojas necesarias existan.
    hojas_faltantes = [
        tabla
        for tabla in TABLAS_DIMENSIONES
        if tabla not in hojas_disponibles
    ]

    if hojas_faltantes:
        raise ValueError(
            f"No se encontraron estas hojas en el Excel: "
            f"{hojas_faltantes}\n"
            f"Hojas disponibles: {hojas_disponibles}"
        )

    print("\n" + "=" * 60)
    print("CARGA DE DIMENSIONES")
    print("=" * 60)

    # Una sola transacción: si una dimensión falla,
    # se revierten las cargas de esta ejecución.
    with engine.begin() as connection:

        for tabla in TABLAS_DIMENSIONES:

            print(f"\nProcesando {tabla}...")

            # Leer la hoja correspondiente.
            df = pd.read_excel(
                excel,
                sheet_name=tabla
            )

            cantidad_registros = len(df)

            # Insertar registros en la tabla existente.
            df.to_sql(
                name=tabla,
                con=connection,
                schema="public",
                if_exists="append",
                index=False,
                chunksize=500
            )

            print(f"Registros insertados: {cantidad_registros}")

    print("\n" + "=" * 60)
    print("CARGA DE DIMENSIONES COMPLETADA")
    print("=" * 60)


# ============================================================
# 5. VERIFICACIÓN DE REGISTROS
# ============================================================

def verificar_carga(engine):
    """Consulta la cantidad de registros de cada dimensión."""

    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE LA CARGA")
    print("=" * 60)

    with engine.connect() as connection:

        for tabla in TABLAS_DIMENSIONES:

            consulta = text(
                f'SELECT COUNT(*) FROM public."{tabla}"'
            )

            cantidad = connection.execute(
                consulta
            ).scalar_one()

            print(f"{tabla}: {cantidad} registros")


# ============================================================
# 6. PROGRAMA PRINCIPAL
# ============================================================

def main():

    engine = None

    try:
        print("Iniciando carga de dimensiones...\n")

        validar_archivo()

        engine = crear_conexion()

        # Comprobar conexión.
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("Conexión con PostgreSQL establecida.")

        cargar_dimensiones(engine)

        verificar_carga(engine)

    except Exception as error:
        print("\nERROR DURANTE LA CARGA")
        print(error)

    finally:
        if engine is not None:
            engine.dispose()

        print("\nProceso finalizado.")


if __name__ == "__main__":
    main()
