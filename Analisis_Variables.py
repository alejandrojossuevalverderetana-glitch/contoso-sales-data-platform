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
    3. Estimación de la función de densidad (histograma, KDE y ajuste teórico).
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
from matplotlib.colors import TwoSlopeNorm
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

# Colores y nombres usados en todas las gráficas (un color fijo por variable)
COLORES = {
    "Cantidad_total": "#2E6F9E",
    "Precio_unitario": "#3B8E5A",
    "Ingresos": "#D9822B",
}
COLOR_KDE = "#1B1B1B"
COLOR_AJUSTE = "#C0392B"
ETIQUETAS = {
    "Cantidad_total": "Cantidad total (unidades)",
    "Precio_unitario": "Precio unitario",
    "Ingresos": "Ingresos",
}
# Frases con su artículo, para que los títulos queden bien redactados
TITULOS = {
    "Cantidad_total": "de la cantidad total",
    "Precio_unitario": "del precio unitario",
    "Ingresos": "de los ingresos",
}

# Distribuciones teóricas candidatas para el ajuste
DISTRIBUCIONES = {
    "Normal": stats.norm,
    "Exponencial": stats.expon,
    "Log-normal": stats.lognorm,
    "Gamma": stats.gamma,
}


# ----------------------------------------------------------------------------
# ESTILO DE LAS GRÁFICAS
# ----------------------------------------------------------------------------
def configurar_estilo():
    """Define un estilo limpio y legible para todas las figuras del reporte."""
    plt.rcParams.update({
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "legend.frameon": False,
        "legend.fontsize": 10,
    })


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
    # ORDER BY garantiza siempre el mismo orden de filas: sin él, PostgreSQL puede
    # entregarlas en otro orden y la muestra aleatoria (y los parámetros del ajuste)
    # cambiarían de una corrida a otra.
    consulta = text(
        'SELECT "Cantidad_total", "Precio_unitario", "Ingresos" '
        'FROM "FactSales" ORDER BY "OrderID"'
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
def graficar_densidad(datos, muestra, ajustes):
    """
    Grafica la estimación de la función de densidad de cada variable:
        - Histograma normalizado (área total = 1): aproxima la densidad.
        - KDE (estimación por kernel gaussiano): versión suavizada.
        - Curva de la distribución teórica con mejor ajuste (ver ajustar_distribuciones).
    Panel izquierdo: escala original, recortada al percentil 99 para ver el cuerpo
    de la distribución. Panel derecho: logaritmo de la variable; si la forma resulta
    simétrica, la variable original se parece a una log-normal.
    Además se grafica la función de masa de probabilidad (PMF) de Cantidad_total,
    que es una variable discreta.
    """
    CARPETA_RESULTADOS.mkdir(exist_ok=True)

    for var in VARIABLES:
        x = datos[var].to_numpy(dtype=float)
        x_muestra = muestra[var].to_numpy(dtype=float)
        color = COLORES[var]
        limite = np.percentile(x, 99)

        fig, ejes = plt.subplots(1, 2, figsize=(13, 5))

        # ---- Panel izquierdo: escala original ----
        eje = ejes[0]
        if var == "Cantidad_total":
            # Variable entera: una barra por cada valor entero
            bordes_hist = np.arange(np.floor(x.min()), limite + 2) - 0.5
        else:
            bordes_hist = np.linspace(x.min(), limite, 61)
        conteos, bordes = np.histogram(x[x <= limite], bins=bordes_hist)
        # Densidad calculada respecto al total de datos (no solo al recorte)
        densidad = conteos / (len(x) * np.diff(bordes))
        eje.bar(bordes[:-1], densidad, width=np.diff(bordes), align="edge",
                color=color, alpha=0.55, label="Histograma")

        malla = np.linspace(x.min(), limite, 500)
        eje.plot(malla, stats.gaussian_kde(x_muestra)(malla), color=COLOR_KDE,
                 linewidth=2, label="KDE")

        nombre, dist, parametros = ajustes[var]
        eje.plot(malla, dist.pdf(malla, *parametros), color=COLOR_AJUSTE,
                 linewidth=2, linestyle="--", label=f"Ajuste {nombre}")

        eje.set_ylim(0, densidad.max() * 1.25)  # evita que el ajuste se salga de la figura
        eje.set_title(f"Densidad {TITULOS[var]}\n(hasta el percentil 99)")
        eje.set_xlabel(ETIQUETAS[var])
        eje.set_ylabel("Densidad de probabilidad")
        eje.legend()

        # ---- Panel derecho: escala logarítmica ----
        eje = ejes[1]
        log_x = np.log(x)
        if var == "Cantidad_total":
            # Variable entera: con intervalos de igual ancho en escala logarítmica
            # quedarían intervalos sin ningún entero (huecos artificiales). Se usan
            # intervalos cuyos bordes son enteros, de modo que todos contengan datos.
            enteros = np.unique(np.floor(np.geomspace(x.min(), x.max() + 1, 30)).astype(int))
            bordes_log = np.log(enteros - 0.5)
        else:
            bordes_log = 60
        eje.hist(log_x, bins=bordes_log, density=True, color=color, alpha=0.55,
                 label="Histograma")
        if var != "Cantidad_total":
            # Para la variable discreta la KDE genera picos artificiales, no se grafica
            malla_log = np.linspace(log_x.min(), log_x.max(), 500)
            eje.plot(malla_log, stats.gaussian_kde(np.log(x_muestra))(malla_log),
                     color=COLOR_KDE, linewidth=2, label="KDE")
        eje.set_title(f"Logaritmo {TITULOS[var]}")
        eje.set_xlabel(f"log({ETIQUETAS[var].split(' (')[0]})")  # sin la unidad entre paréntesis
        eje.set_ylabel("Densidad de probabilidad")
        eje.legend()

        fig.tight_layout()
        ruta = CARPETA_RESULTADOS / f"densidad_{var}.png"
        fig.savefig(ruta)
        plt.close(fig)
        print(f"Figura guardada: {ruta}")

    # ---- Función de masa de probabilidad de Cantidad_total ----
    pmf = datos["Cantidad_total"].value_counts(normalize=True).sort_index()
    corta = pmf[pmf.index <= 40]
    fig, eje = plt.subplots(figsize=(10, 5))
    eje.bar(corta.index, corta.values, width=0.8, color=COLORES["Cantidad_total"])
    for valor, prob in corta.nlargest(3).items():
        # Si la barra vecina es más alta, la etiqueta se corre hacia el lado contrario
        # para no montarse sobre ella.
        if corta.get(valor + 1, 0) > prob:
            alineacion, desplazamiento = "right", 3
        elif corta.get(valor - 1, 0) > prob:
            alineacion, desplazamiento = "left", -3
        else:
            alineacion, desplazamiento = "center", 0
        eje.annotate(f"{prob:.1%}", (valor, prob), xytext=(desplazamiento, 2),
                     textcoords="offset points", ha=alineacion, va="bottom", fontsize=10)
    eje.set_title("Función de masa de probabilidad de la cantidad total")
    eje.set_xlabel(ETIQUETAS["Cantidad_total"])
    eje.set_ylabel("Probabilidad P(X = x)")
    eje.text(0.98, 0.95, f"Los valores hasta 40 unidades\nson el {corta.sum():.1%} de las ventas",
             transform=eje.transAxes, ha="right", va="top", fontsize=10)
    fig.tight_layout()
    ruta = CARPETA_RESULTADOS / "pmf_Cantidad_total.png"
    fig.savefig(ruta)
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

    mejores = {}  # variable -> (nombre, distribución, parámetros) del mejor ajuste

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

        mejor = tabla.loc[0, "Distribución"]
        mejores[var] = (mejor, *parametros_ajustados[mejor])

    return mejores


# ----------------------------------------------------------------------------
# 5. DEPENDENCIA ENTRE VARIABLES
# ----------------------------------------------------------------------------
def agrupar_en_deciles(serie, entera):
    """
    Agrupa una variable en hasta 10 grupos con la misma cantidad de datos (deciles)
    y devuelve una variable categórica con etiquetas legibles, por ejemplo "10"
    o "16–24" para variables enteras, y "66–200" para variables continuas.
    """
    codigos, bordes = pd.qcut(serie, q=10, labels=False, retbins=True, duplicates="drop")
    n_grupos = len(bordes) - 1
    etiquetas = []
    for i in range(n_grupos):
        inferior, superior = bordes[i], bordes[i + 1]
        if entera:
            # Los intervalos de qcut son (inferior, superior]; el primero incluye el mínimo
            ini = int(np.ceil(inferior)) if i == 0 else int(np.floor(inferior)) + 1
            fin = int(np.floor(superior))
            if i == n_grupos - 1:
                etiquetas.append(f"{ini}+")
            elif ini == fin:
                etiquetas.append(f"{ini}")
            else:
                etiquetas.append(f"{ini}–{fin}")
        else:
            etiquetas.append(f"{inferior:,.0f}–{superior:,.0f}")
    return pd.Categorical.from_codes(codigos, categories=etiquetas, ordered=True)


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
    q_grupos = agrupar_en_deciles(datos["Cantidad_total"], entera=True)
    p_grupos = agrupar_en_deciles(datos["Precio_unitario"], entera=False)
    q_etiquetas = list(q_grupos.categories)
    p_etiquetas = list(p_grupos.categories)

    tabla = pd.crosstab(
        pd.Series(q_grupos, index=datos.index, name="Cantidad"),
        pd.Series(p_grupos, index=datos.index, name="Precio"),
    ).reindex(index=q_etiquetas, columns=p_etiquetas)

    chi2, p_valor, grados, esperada = stats.chi2_contingency(tabla)
    n = tabla.to_numpy().sum()
    # V de Cramér: mide la fuerza de la asociación (0 = ninguna, 1 = total).
    # Con millones de datos el p-valor es siempre ínfimo, por eso se reporta V.
    v_cramer = np.sqrt(chi2 / (n * (min(tabla.shape) - 1)))
    print("\nd) Prueba chi-cuadrado de independencia (variables agrupadas en deciles)")
    print(f"   chi2 = {chi2:,.1f} | grados de libertad = {grados} | p-valor = {p_valor:.3g}")
    print(f"   V de Cramér = {v_cramer:.4f}")

    # ---- e) Cómo cambia el precio según la cantidad ----
    por_grupo = (
        pd.DataFrame({"grupo": q_grupos, "precio": datos["Precio_unitario"].to_numpy()})
        .groupby("grupo", observed=True)["precio"].agg(["count", "mean", "median"])
    )
    print("\ne) Precio_unitario según el grupo de Cantidad_total")
    print(por_grupo.to_string(float_format=lambda v: f"{v:,.2f}"))

    # ---- f) Razón entre frecuencia observada y esperada bajo independencia ----
    razon = tabla / esperada
    razon.to_csv(CARPETA_RESULTADOS / "dependencia_razon_observada_esperada.csv",
                 float_format="%.4f")

    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    graficar_mapa_calor(razon)
    graficar_cajas(datos, q_grupos, q_etiquetas)

    # Se guarda un CSV con los resultados numéricos para el reporte
    pd.DataFrame({
        "E[Q]": [e_q], "E[P]": [e_p], "E[Ingresos]": [e_ingresos],
        "R_QP=E[QP]": [correlacion_qp], "E[Q]E[P]": [producto_medias],
        "Cov(Q,P)": [covarianza], "Pearson": [pearson], "Spearman": [spearman],
        "chi2": [chi2], "V_Cramer": [v_cramer],
    }).to_csv(CARPETA_RESULTADOS / "dependencia.csv", index=False, float_format="%.6f")


def graficar_mapa_calor(razon):
    """
    Mapa de calor de la razón (frecuencia observada / frecuencia esperada si Q y P
    fueran independientes). Un valor de 1 indica independencia; mayor a 1 indica
    que esa combinación ocurre más de lo esperado, y menor a 1, que ocurre menos.
    """
    valores = razon.to_numpy()
    norma = TwoSlopeNorm(vcenter=1.0, vmin=min(valores.min(), 0.5),
                         vmax=max(valores.max(), 1.5))

    fig, eje = plt.subplots(figsize=(12, 6.5))
    imagen = eje.imshow(valores, cmap="RdBu_r", norm=norma, aspect="auto")
    eje.grid(False)

    eje.set_xticks(range(valores.shape[1]))
    eje.set_xticklabels(razon.columns, rotation=45, ha="right")
    eje.set_yticks(range(valores.shape[0]))
    eje.set_yticklabels(razon.index)
    eje.set_xlabel("Grupo de precio unitario (deciles)")
    eje.set_ylabel("Grupo de cantidad total (unidades)")
    eje.set_title("Dependencia entre cantidad y precio\n"
                  "Frecuencia observada / frecuencia esperada si fueran independientes")

    for i in range(valores.shape[0]):
        for j in range(valores.shape[1]):
            intensidad = norma(valores[i, j])
            color_texto = "white" if intensidad < 0.2 or intensidad > 0.8 else "black"
            eje.text(j, i, f"{valores[i, j]:.2f}", ha="center", va="center",
                     fontsize=9, color=color_texto)

    barra = fig.colorbar(imagen, ax=eje)
    barra.set_label("Razón observada / esperada (1 = independencia)")
    fig.tight_layout()
    ruta = CARPETA_RESULTADOS / "dependencia_mapa_calor.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"\nFigura guardada: {ruta}")


def graficar_cajas(datos, q_grupos, q_etiquetas):
    """Diagrama de cajas del precio unitario para cada grupo de cantidad total."""
    precio = datos["Precio_unitario"].to_numpy(dtype=float)
    codigos = np.asarray(q_grupos.codes)
    grupos = [precio[codigos == i] for i in range(len(q_etiquetas))]
    posiciones = np.arange(1, len(q_etiquetas) + 1)

    fig, eje = plt.subplots(figsize=(11, 6))
    eje.boxplot(grupos, whis=(5, 95), showfliers=False, patch_artist=True,
                boxprops={"facecolor": COLORES["Precio_unitario"], "alpha": 0.55},
                medianprops={"color": COLOR_KDE, "linewidth": 2})
    eje.plot(posiciones, [g.mean() for g in grupos], "D", color=COLOR_AJUSTE,
             markersize=7, label="Media")
    eje.set_yscale("log")
    eje.set_xticks(posiciones)
    eje.set_xticklabels(q_etiquetas)
    eje.set_xlabel("Grupo de cantidad total (unidades)")
    eje.set_ylabel("Precio unitario (escala logarítmica)")
    eje.set_title("Precio unitario según el grupo de cantidad total")
    eje.legend(loc="upper right")
    fig.text(0.01, -0.01,
             "La caja abarca del percentil 25 al 75; la línea es la mediana; "
             "los bigotes llegan a los percentiles 5 y 95.",
             fontsize=9, color="dimgray")
    fig.tight_layout()
    ruta = CARPETA_RESULTADOS / "dependencia_cajas.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"Figura guardada: {ruta}")


# ----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------------
def main():
    configurar_estilo()

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

    # 3) Ajuste de distribuciones teóricas
    ajustes = ajustar_distribuciones(muestra)

    # 4) Función de densidad (histograma, KDE y mejor ajuste teórico)
    print("\n" + "=" * 78)
    print("FIGURAS DE LA FUNCIÓN DE DENSIDAD")
    print("=" * 78)
    graficar_densidad(datos, muestra, ajustes)

    # 5) Dependencia entre Cantidad_total y Precio_unitario
    analizar_dependencia(datos, muestra)


if __name__ == "__main__":
    main()