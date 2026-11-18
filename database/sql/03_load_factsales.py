
"""
Proyecto: Contoso Sales
Archivo: 03_load_factsales.py

Descripción:
Carga los registros de FactSales.txt hacia PostgreSQL
utilizando COPY y lectura por bloques.
"""

from pathlib import Path
from getpass import getpass
from io import StringIO
import csv

import pandas as pd
import psycopg2
from psycopg2 import sql


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
RUTA_FACTSALES = BASE_DIR / "FactSales.txt"

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "contoso_sales",
    "username": "postgres"
}

TAMANO_BLOQUE = 100_000

COLUMNAS_FACTSALES = [
    "OrderID",
    "DateKey",
    "channelKey",
    "StoreKey",
    "ProductKey",
    "PromotionKey",
    "SalesQuantity",
    "ReturnQuantity",
    "Cantidad_total",
    "Devolución",
    "Venta_type",
    "Devolución_type",
    "Precio_unitario",
    "Ingresos"
]

TABLA = "FactSales"


# ============================================================
# CONEXIÓN
# ============================================================

def crear_conexion():
    password = getpass("Contraseña de PostgreSQL: ")

    connection = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["database"],
        user=DB_CONFIG["username"],
        password=password
    )

    return connection


# ============================================================
# VALIDACIONES INICIALES
# ============================================================

def validar_archivo():
    if not RUTA_FACTSALES.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {RUTA_FACTSALES}"
        )

    print(f"Archivo encontrado: {RUTA_FACTSALES.name}")
    print(f"Tamaño: {RUTA_FACTSALES.stat().st_size / (1024**2):.2f} MB")


def detectar_separador():
    with open(RUTA_FACTSALES, "r", encoding="utf-8-sig", newline="") as archivo:
        muestra = archivo.read(10000)

    try:
        dialecto = csv.Sniffer().sniff(
            muestra,
            delimiters="\t;,|"
        )
        separador = dialecto.delimiter
    except csv.Error:
        separador = "\t"

    print(f"Separador detectado: {repr(separador)}")

    return separador


def validar_columnas(separador):
    encabezado = pd.read_csv(
        RUTA_FACTSALES,
        sep=separador,
        nrows=0,
        encoding="utf-8-sig"
    )

    columnas_archivo = encabezado.columns.tolist()

    if columnas_archivo != COLUMNAS_FACTSALES:
        raise ValueError(
            "\nLas columnas de FactSales.txt no coinciden con "
            "las esperadas.\n\n"
            f"Columnas encontradas:\n{columnas_archivo}\n\n"
            f"Columnas esperadas:\n{COLUMNAS_FACTSALES}"
        )

    print("Estructura de columnas validada correctamente.")


# ============================================================
# CARGA DE DATOS
# ============================================================

def cargar_factsales(connection, separador):

    consulta_conteo = 'SELECT COUNT(*) FROM public."FactSales"'

    with connection.cursor() as cursor:
        cursor.execute(consulta_conteo)
        registros_existentes = cursor.fetchone()[0]

    if registros_existentes > 0:
        raise RuntimeError(
            f"La tabla FactSales ya contiene {registros_existentes} "
            "registros. Se cancela la carga para evitar duplicados."
        )

    print("\n" + "=" * 60)
    print("CARGA DE FACTSALES")
    print("=" * 60)

    total_insertados = 0

    bloques = pd.read_csv(
    RUTA_FACTSALES,
    sep=separador,
    encoding="utf-8-sig",
    chunksize=TAMANO_BLOQUE,
    parse_dates=["DateKey"],
    dayfirst=True
)

    nombres_columnas = sql.SQL(", ").join(
        sql.Identifier(columna)
        for columna in COLUMNAS_FACTSALES
    )

    consulta_copy = sql.SQL(
        """
        COPY public.{} ({})
        FROM STDIN
        WITH (
            FORMAT CSV,
            DELIMITER E'\\t',
            NULL '\\N',
            QUOTE '"',
            ESCAPE '"'
        )
        """
    ).format(
        sql.Identifier(TABLA),
        nombres_columnas
    )

    with connection.cursor() as cursor:

        for numero_bloque, df in enumerate(bloques, start=1):

            # Asegurar el orden de las columnas
            df = df[COLUMNAS_FACTSALES]

            # Limpiar y convertir valores numéricos
            columnas_numericas = [
                "Precio_unitario",
                "Ingresos"
            ]

            for columna in columnas_numericas:
                df[columna] = (
                    df[columna]
                    .astype("string")
                    .str.replace("\u00a0", "", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.strip()
                    .str.replace(",", ".", regex=False)
                )

                df[columna] = pd.to_numeric(
                    df[columna],
                    errors="raise"
                )

            # Convertir fechas al formato ISO
            df["DateKey"] = df["DateKey"].dt.strftime("%Y-%m-%d")

            # Preparar bloque para COPY
            buffer = StringIO()

            df.to_csv(
                buffer,
                sep="\t",
                index=False,
                header=False,
                na_rep=r"\N",
                quoting=csv.QUOTE_MINIMAL,
                doublequote=True
            )

            buffer.seek(0)

            cursor.copy_expert(
                consulta_copy.as_string(connection),
                buffer
            )

            cantidad = len(df)
            total_insertados += cantidad

            print(
                f"Bloque {numero_bloque}: "
                f"{cantidad:,} registros | "
                f"Total: {total_insertados:,}"
            )

    return total_insertados


# ============================================================
# VERIFICACIÓN
# ============================================================

def verificar_carga(connection, total_esperado):

    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM public."FactSales"')
        total_bd = cursor.fetchone()[0]

    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE LA CARGA")
    print("=" * 60)

    print(f"Registros procesados: {total_esperado:,}")
    print(f"Registros en PostgreSQL: {total_bd:,}")

    if total_bd != total_esperado:
        raise RuntimeError(
            "La cantidad de registros en PostgreSQL no coincide "
            "con la cantidad procesada."
        )

    print("\nCarga verificada correctamente.")


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    connection = None

    try:
        print("Iniciando carga de FactSales...\n")

        validar_archivo()

        separador = detectar_separador()

        validar_columnas(separador)

        connection = crear_conexion()
        connection.autocommit = False

        print("\nConexión con PostgreSQL establecida.")

        total_insertados = cargar_factsales(
            connection,
            separador
        )

        verificar_carga(
            connection,
            total_insertados
        )

        connection.commit()

        print("\n" + "=" * 60)
        print("CARGA DE FACTSALES COMPLETADA")
        print("=" * 60)

    except Exception as error:

        if connection is not None:
            connection.rollback()

        print("\nERROR DURANTE LA CARGA")
        print(repr(error))
        print("\nLa transacción fue revertida.")

    finally:

        if connection is not None:
            connection.close()

        print("\nProceso finalizado.")


if __name__ == "__main__":
    main()
