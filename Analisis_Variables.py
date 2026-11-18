"""
Proyecto 01 - Principios de Análisis de Datos (Contoso Sales)
Modelos Probabilísticos de Señales y Sistemas - II-2026

Parte 2: Análisis estadístico y probabilístico de las variables aleatorias.

Variables analizadas (tabla FactSales):
    - Cantidad_total   : unidades vendidas menos unidades devueltas (discreta)
    - Precio_unitario  : precio de una unidad (continua)
    - Ingresos         : Precio_unitario * Cantidad_total (continua)

Este script realiza:
    1. Preparación y verificación de las tres variables.
    2. Estadísticos: media, mediana, varianza, momentos, asimetría y curtosis.
    3. Estimación de la función de densidad (histograma y KDE).
    4. Ajuste de distribuciones teóricas candidatas (con sus parámetros).
    5. Dependencia entre Cantidad_total y Precio_unitario, y comprobación de que
       E[Ingresos] = E[Cantidad_total * Precio_unitario] (correlación).

Los datos se leen desde la base de datos PostgreSQL contoso_sales
(ver la carpeta database/ del repositorio para crearla y cargarla).

Requisitos:
    pip install pandas sqlalchemy psycopg2-binary scipy matplotlib

Uso:
    Ejecutar:  python3 Analisis_Variables.py
    El script pide la contraseña de PostgreSQL al iniciar; no se guarda en el código.
"""

from getpass import getpass
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # genera las figuras como archivos, sin abrir ventanas
import matplotlib.pyplot as plt
from scipy import stats
from sqlalchemy import create_engine, text, URL

# ----------------------------------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------------------------------
# Parámetros de conexión a PostgreSQL. Ajustar el puerto y el usuario según la
# instalación local (en Ubuntu el puerto por defecto es 5432).
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "contoso_sales",
    "username": "postgres",
}

CARPETA_RESULTADOS = Path("resultados")

VARIABLES = ["Cantidad_total", "Precio_unitario", "Ingresos"]

# Con 2.28 millones de datos, estimar la KDE y ajustar distribuciones sobre todo
# el conjunto es muy lento. Se usa una muestra aleatoria reproducible.
TAMANO_MUESTRA = 50_000
SEMILLA = 42  # semilla fija para obtener siempre los mismos resultados

# Distribuciones teóricas candidatas para el ajuste
DISTRIBUCIONES = {
    "Normal": stats.norm,
    "Exponencial": stats.expon,
    "Log-normal": stats.lognorm,
    "Gamma": stats.gamma,
}


# ----------------------------------------------------------------------------
# 1. PREPARACIÓN DE LAS VARIABLES
# ----------------------------------------------------------------------------
def crear_motor():
    """Crea la conexión con PostgreSQL pidiendo la contraseña por teclado."""
    password = getpass("Contraseña de PostgreSQL: ")
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_CONFIG["username"],
        password=password,
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
    )
    return create_engine(url)


def cargar_datos(motor):
    """
    Devuelve un DataFrame con las tres variables de interés, leídas desde la
    tabla FactSales de la base de datos. Es el único lugar donde se leen los datos.
    """
    # Los nombres van entre comillas dobles porque en PostgreSQL conservan
    # las mayúsculas solo si se escriben así.
    consulta = text(
        'SELECT "Cantidad_total", "Precio_unitario", "Ingresos" FROM "FactSales"'
    )
    with motor.connect() as conexion:
        datos = pd.read_sql(consulta, conexion)

    # PostgreSQL entrega las columnas NUMERIC como Decimal; se pasan a float
    # para poder calcular los estadísticos.
    datos["Precio_unitario"] = datos["Precio_unitario"].astype(float)
    datos["Ingresos"] = datos["Ingresos"].astype(float)
    datos["Cantidad_total"] = datos["Cantidad_total"].astype(int)
    return datos[VARIABLES].copy()


def verificar_variables(datos):
    """Comprueba que Ingresos = Precio_unitario * Cantidad_total y que no hay faltantes."""
    print("=" * 78)
    print("VERIFICACIÓN DE LAS VARIABLES")
    print("=" * 78)
    print(f"Registros: {len(datos):,}")
    print(f"Datos faltantes por variable:\n{datos.isna().sum().to_string()}")

    # Si Ingresos coincide con precio * cantidad, la relación entre las tres
    # variables es exacta y no hay que corregir nada.
    diferencia = (datos["Ingresos"] - datos["Precio_unitario"] * datos["Cantidad_total"]).abs()
    print(f"\nDiferencia máxima |Ingresos - Precio*Cantidad|: {diferencia.max():.4f}")


# ----------------------------------------------------------------------------
# 2. ESTADÍSTICOS Y MOMENTOS
# ----------------------------------------------------------------------------
def momento_central(x, k):
    """Momento central de orden k:  mu_k = E[(X - E[X])^k]."""
    return np.mean((x - np.mean(x)) ** k)


def calcular_estadisticos(x):
    """
    Calcula los estadísticos de una variable a partir de sus momentos.
        media           = E[X]
        varianza        = mu_2 = E[(X - media)^2]
        asimetría       = mu_3 / sigma^3
        curtosis        = mu_4 / sigma^4        (vale 3 para una normal)
        exceso curtosis = curtosis - 3
    """
    x = np.asarray(x, dtype=float)
    media = np.mean(x)
    mu2 = momento_central(x, 2)  # varianza poblacional
    mu3 = momento_central(x, 3)
    mu4 = momento_central(x, 4)
    sigma = np.sqrt(mu2)

    return {
        "Mínimo": np.min(x),
        "Máximo": np.max(x),
        "Media": media,
        "Mediana": np.median(x),
        "Varianza": mu2,
        "Desviación estándar": sigma,
        "Momento central 3": mu3,
        "Momento central 4": mu4,
        "Asimetría": mu3 / sigma ** 3,
        "Curtosis": mu4 / sigma ** 4,
        "Exceso de curtosis": mu4 / sigma ** 4 - 3,
    }


def reporte_estadisticos(datos):
    """Calcula y muestra los estadísticos de las tres variables en una tabla."""
    print("\n" + "=" * 78)
    print("ESTADÍSTICOS Y MOMENTOS")
    print("=" * 78)

    resultados = {var: calcular_estadisticos(datos[var]) for var in VARIABLES}
    tabla = pd.DataFrame(resultados)
    print(tabla.to_string(float_format=lambda v: f"{v:,.4f}"))

    # Comprobación cruzada con las funciones de scipy
    print("\nComprobación con scipy (deben coincidir con la tabla):")
    for var in VARIABLES:
        asim = stats.skew(datos[var])
        curt = stats.kurtosis(datos[var], fisher=False)
        print(f"  {var}: asimetría = {asim:.4f} | curtosis = {curt:.4f}")

    # La relación entre media y mediana orienta sobre la forma de la distribución
    print("\nInterpretación inicial (media vs mediana):")
    for var in VARIABLES:
        media, mediana = tabla.loc["Media", var], tabla.loc["Mediana", var]
        lado = "derecha" if media > mediana else "izquierda"
        print(f"  {var}: media {media:,.2f} vs mediana {mediana:,.2f} -> cola hacia la {lado}")

    return tabla


# ----------------------------------------------------------------------------
# 3. FUNCIÓN DE DENSIDAD
# ----------------------------------------------------------------------------
def graficar_densidad(datos, muestra):
    """
    Estima la función de densidad de cada variable:
        - Histograma normalizado (área total = 1): aproxima la densidad.
        - KDE (estimación por kernel gaussiano): versión suavizada de la densidad.
    Para Cantidad_total, que es discreta, se grafica además su función de masa
    de probabilidad (PMF) con las frecuencias relativas.
    """
    CARPETA_RESULTADOS.mkdir(exist_ok=True)

    for var in VARIABLES:
        x_completo = datos[var].to_numpy()
        x_muestra = muestra[var].to_numpy()

        fig, ejes = plt.subplots(1, 2, figsize=(12, 4.5))

        # Izquierda: escala normal, recortada al percentil 99 para ver el cuerpo
        # de la distribución (los valores extremos aplastan el gráfico).
        limite = np.percentile(x_completo, 99)
        ejes[0].hist(x_completo[x_completo <= limite], bins=60, density=True,
                     alpha=0.6, label="Histograma (densidad)")
        malla = np.linspace(x_muestra.min(), limite, 400)
        kde = stats.gaussian_kde(x_muestra)
        ejes[0].plot(malla, kde(malla), linewidth=2, label="KDE")
        ejes[0].set_title(f"{var} (hasta el percentil 99)")
        ejes[0].set_xlabel(var)
        ejes[0].set_ylabel("Densidad")
        ejes[0].legend()

        # Derecha: logaritmo de la variable. Si la forma resulta simétrica,
        # la variable original se parece a una log-normal.
        log_x = np.log(x_completo)
        ejes[1].hist(log_x, bins=60, density=True, alpha=0.6, label="Histograma")
        malla_log = np.linspace(log_x.min(), log_x.max(), 400)
        kde_log = stats.gaussian_kde(np.log(x_muestra))
        ejes[1].plot(malla_log, kde_log(malla_log), linewidth=2, label="KDE")
        ejes[1].set_title(f"log({var})")
        ejes[1].set_xlabel(f"log({var})")
        ejes[1].set_ylabel("Densidad")
        ejes[1].legend()

        fig.tight_layout()
        ruta = CARPETA_RESULTADOS / f"densidad_{var}.png"
        fig.savefig(ruta, dpi=150)
        plt.close(fig)
        print(f"Figura guardada: {ruta}")

    # PMF de la variable discreta Cantidad_total (valores más frecuentes)
    pmf = datos["Cantidad_total"].value_counts(normalize=True).sort_index()
    fig, eje = plt.subplots(figsize=(9, 4.5))
    pmf_corta = pmf[pmf.index <= 100]
    eje.bar(pmf_corta.index, pmf_corta.values)
    eje.set_title("Función de masa de probabilidad de Cantidad_total (valores hasta 100)")
    eje.set_xlabel("Cantidad_total")
    eje.set_ylabel("P(X = x)")
    fig.tight_layout()
    ruta = CARPETA_RESULTADOS / "pmf_Cantidad_total.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    print(f"Figura guardada: {ruta}")
    print(f"  Cantidad_total toma {len(pmf)} valores distintos; "
          f"P(X <= 100) = {pmf[pmf.index <= 100].sum():.4f}")


# ----------------------------------------------------------------------------
# 4. AJUSTE DE DISTRIBUCIONES TEÓRICAS
# ----------------------------------------------------------------------------
def ajustar_distribuciones(muestra):
    """
    Ajusta cada distribución candidata por máxima verosimilitud y la compara con
    los datos mediante el estadístico de Kolmogorov-Smirnov (KS).

    El estadístico KS es la mayor distancia entre la función de distribución
    acumulada de los datos y la del modelo: menor valor significa mejor ajuste.
    Se usa como medida de distancia y no como prueba de hipótesis, pues con
    tantos datos cualquier modelo sería rechazado.
    """
    print("\n" + "=" * 78)
    print(f"AJUSTE DE DISTRIBUCIONES (muestra de {len(muestra):,} datos)")
    print("=" * 78)

    for var in VARIABLES:
        x = muestra[var].to_numpy(dtype=float)
        filas = []
        parametros_ajustados = {}
        for nombre, dist in DISTRIBUCIONES.items():
            try:
                # Las variables son positivas: para Gamma y Log-normal se fija la
                # ubicación en 0 (floc=0). Sin esto el ajuste puede no converger.
                if nombre in ("Gamma", "Log-normal"):
                    parametros = dist.fit(x, floc=0)
                else:
                    parametros = dist.fit(x)
                ks = stats.kstest(x, dist.cdf, args=parametros).statistic
                # Log-verosimilitud: mayor (menos negativa) es mejor
                logver = np.sum(dist.logpdf(x, *parametros))
                filas.append({"Distribución": nombre, "KS": ks, "Log-verosimilitud": logver})
                parametros_ajustados[nombre] = (dist, parametros)
            except Exception as error:
                print(f"  No se pudo ajustar {nombre} a {var}: {error}")

        tabla = pd.DataFrame(filas).sort_values("KS").reset_index(drop=True)
        print(f"\n{var}:")
        print(tabla.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
        print(f"  Mejor ajuste según KS: {tabla.loc[0, 'Distribución']}")

        # Parámetros de cada distribución: son los que definen la expresión de
        # la función de densidad f(x) que se reporta.
        print("  Parámetros ajustados:")
        for nombre, (dist, parametros) in parametros_ajustados.items():
            etiquetas = (dist.shapes.split(", ") if dist.shapes else []) + ["loc", "scale"]
            texto = ", ".join(f"{e} = {v:,.6g}" for e, v in zip(etiquetas, parametros))
            print(f"    {nombre}: {texto}")


# ----------------------------------------------------------------------------
# 5. DEPENDENCIA ENTRE VARIABLES
# ----------------------------------------------------------------------------
def analizar_dependencia(datos, muestra):
    """
    Analiza la relación entre Q = Cantidad_total y P = Precio_unitario.

    Si Q y P fueran independientes, se cumpliría  E[Q*P] = E[Q] * E[P].
    La diferencia entre ambos lados es la covarianza:
        Cov(Q, P) = E[Q*P] - E[Q]*E[P]
    Como Ingresos = Q * P, el valor esperado de Ingresos es la correlación
    (en sentido de procesos estocásticos) R_QP = E[Q*P].
    """
    print("\n" + "=" * 78)
    print("DEPENDENCIA ENTRE Cantidad_total (Q) Y Precio_unitario (P)")
    print("=" * 78)

    q = datos["Cantidad_total"].to_numpy(dtype=float)
    p = datos["Precio_unitario"].to_numpy(dtype=float)
    ingresos = datos["Ingresos"].to_numpy(dtype=float)

    # ---- a) Comprobación pedida: E[Ingresos] = E[Q*P] (correlación) ----
    e_q, e_p = np.mean(q), np.mean(p)
    e_ingresos = np.mean(ingresos)
    correlacion_qp = np.mean(q * p)          # R_QP = E[Q*P]
    producto_medias = e_q * e_p              # E[Q]*E[P]
    covarianza = correlacion_qp - producto_medias

    print("\na) Valor esperado de Ingresos y correlación entre Q y P")
    print(f"   E[Q]               = {e_q:,.4f}")
    print(f"   E[P]               = {e_p:,.4f}")
    print(f"   E[Ingresos]        = {e_ingresos:,.4f}")
    print(f"   R_QP = E[Q*P]      = {correlacion_qp:,.4f}")
    print(f"   |E[Ingresos] - E[Q*P]| = {abs(e_ingresos - correlacion_qp):.6f}  "
          f"({'se cumple' if np.isclose(e_ingresos, correlacion_qp) else 'NO se cumple'})")

    # ---- b) Comparación con el caso de independencia ----
    print("\nb) Comparación con el caso independiente")
    print(f"   E[Q]*E[P]          = {producto_medias:,.4f}")
    print(f"   Cov(Q, P)          = E[Q*P] - E[Q]*E[P] = {covarianza:,.4f}")
    print(f"   Diferencia relativa respecto a E[Q*P]: {covarianza / correlacion_qp:.2%}")

    # ---- c) Coeficientes de correlación ----
    pearson = stats.pearsonr(q, p)[0]        # relación lineal
    spearman = stats.spearmanr(q, p)[0]      # relación monótona (por rangos)
    print("\nc) Coeficientes de correlación")
    print(f"   Pearson  (lineal)   = {pearson:.4f}")
    print(f"   Spearman (monótona) = {spearman:.4f}")
    print("   Nota: independencia implica Cov = 0, pero Cov = 0 no implica "
          "independencia.")

    # ---- d) Prueba de independencia chi-cuadrado sobre una tabla de contingencia ----
    # Se agrupa cada variable en deciles para formar una tabla de contingencia.
    q_bins = pd.qcut(datos["Cantidad_total"], q=10, duplicates="drop")
    p_bins = pd.qcut(datos["Precio_unitario"], q=10, duplicates="drop")
    tabla = pd.crosstab(q_bins, p_bins)
    chi2, p_valor, grados, _ = stats.chi2_contingency(tabla)
    n = tabla.to_numpy().sum()
    # V de Cramér: mide la fuerza de la asociación (0 = ninguna, 1 = total).
    # Con millones de datos el p-valor es siempre ínfimo, por eso se reporta V.
    v_cramer = np.sqrt(chi2 / (n * (min(tabla.shape) - 1)))
    print("\nd) Prueba chi-cuadrado de independencia (variables agrupadas en deciles)")
    print(f"   chi2 = {chi2:,.1f} | grados de libertad = {grados} | p-valor = {p_valor:.3g}")
    print(f"   V de Cramér = {v_cramer:.4f}")

    # ---- e) Cómo cambia el precio según la cantidad ----
    por_grupo = datos.groupby(q_bins, observed=True)["Precio_unitario"].agg(["count", "mean", "median"])
    print("\ne) Precio_unitario según el decil de Cantidad_total")
    print(por_grupo.to_string(float_format=lambda v: f"{v:,.2f}"))

    # ---- f) Gráfico de dispersión (muestra) ----
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    fig, eje = plt.subplots(figsize=(7, 5))
    eje.hexbin(muestra["Cantidad_total"], muestra["Precio_unitario"],
               gridsize=50, bins="log", xscale="log", yscale="log")
    eje.set_title("Cantidad_total vs Precio_unitario (muestra, escala log)")
    eje.set_xlabel("Cantidad_total")
    eje.set_ylabel("Precio_unitario")
    fig.tight_layout()
    ruta = CARPETA_RESULTADOS / "dispersion_cantidad_precio.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    print(f"\nFigura guardada: {ruta}")

    # Se guarda un CSV con los resultados numéricos para el reporte
    pd.DataFrame({
        "E[Q]": [e_q], "E[P]": [e_p], "E[Ingresos]": [e_ingresos],
        "R_QP=E[QP]": [correlacion_qp], "E[Q]E[P]": [producto_medias],
        "Cov(Q,P)": [covarianza], "Pearson": [pearson], "Spearman": [spearman],
        "chi2": [chi2], "V_Cramer": [v_cramer],
    }).to_csv(CARPETA_RESULTADOS / "dependencia.csv", index=False, float_format="%.6f")


# ----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------------
def main():
    # 1) Preparación de las variables
    motor = crear_motor()
    try:
        datos = cargar_datos(motor)
    finally:
        motor.dispose()
    verificar_variables(datos)

    # Muestra aleatoria reproducible para KDE y ajuste de distribuciones
    muestra = datos.sample(n=TAMANO_MUESTRA, random_state=SEMILLA)

    # 2) Estadísticos y momentos (con todos los datos)
    tabla = reporte_estadisticos(datos)
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    tabla.to_csv(CARPETA_RESULTADOS / "estadisticos.csv", float_format="%.6f")

    # 3) Función de densidad
    print("\n" + "=" * 78)
    print("FUNCIÓN DE DENSIDAD")
    print("=" * 78)
    graficar_densidad(datos, muestra)

    # 4) Ajuste de distribuciones teóricas
    ajustar_distribuciones(muestra)

    # 5) Dependencia entre Cantidad_total y Precio_unitario
    analizar_dependencia(datos, muestra)


if __name__ == "__main__":
    main()