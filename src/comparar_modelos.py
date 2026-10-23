"""Compara dos modelos de Gemini midiendo latencia real y costo real.

Los precios, los reintentos y el manejo de cuota vienen de consumir_gemini.py:
este archivo solo decide QUÉ medir y cómo mostrarlo. Cambia el modelo poniendo
AI_MODEL en el entorno antes de cada llamada, y lo restaura al terminar.

Uso:
    python3 src/comparar_modelos.py
"""

import os
import statistics
import time

from consumir_gemini import (
    FECHA_PRECIOS,
    LIMITE_DIARIO_GRATUITO,
    PAUSA_SEGUNDOS,
    PRECIOS_POR_MILLON,
    REINTENTOS,
    CuotaAgotada,
    Presupuesto,
    PresupuestoAgotado,
    armar_peticion,
    calcular_costo,
    enviar_con_reintento,
    extraer_texto,
    precios_del_modelo,
)

# ---------------------------------------------------------------------------
# Configuración de esta comparación
# ---------------------------------------------------------------------------

# Modelos a comparar y su nombre para mostrar. Los precios NO van acá: se toman
# de PRECIOS_POR_MILLON en consumir_gemini.py, que es la única fuente.
MODELOS = {
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
}

# Pregunta única para medir latencia (la misma para todos los modelos).
PREGUNTA_LATENCIA = "Confirma en una frase corta que esta conexión funciona"

# Preguntas representativas de lo que la miniaplicación necesita responder.
# Cámbialas por las tuyas: la calidad se evalúa sobre TU caso, no en abstracto.
PREGUNTAS_CALIDAD = [
    "Explica en dos frases qué es un token en un modelo de lenguaje.",
    "Resume en tres puntos por qué conviene separar el manejo de errores en funciones.",
    "¿Qué significa el código HTTP 429 y cómo conviene reaccionar?",
]

REPETICIONES = 4            # mediciones de latencia por modelo (la lección pide 3 o 4)
MINIMO_MEDICIONES = 2       # con menos que esto, el promedio no vale
PRESUPUESTO_POR_MODELO = 16  # tope de peticiones por modelo, bajo el límite diario de 20
VOLUMEN_MENSUAL = 50_000    # el supuesto de la lección, para proyectar


def pedir(pregunta, presupuesto):
    """Hace una petición con reintentos. Devuelve (datos, segundos)."""
    url, headers, body = armar_peticion(pregunta)
    return enviar_con_reintento(url, headers, body, REINTENTOS, presupuesto)


def medir_modelo(modelo, etiqueta):
    """Mide latencia y costo de un modelo. Devuelve un diccionario de resultados."""
    presupuesto = Presupuesto(PRESUPUESTO_POR_MODELO)   # uno nuevo para cada modelo

    os.environ["AI_MODEL"] = modelo
    precio_entrada, precio_salida = precios_del_modelo(modelo)
    entrada_por_millon, salida_por_millon = PRECIOS_POR_MILLON[modelo]

    print(f"\n{'=' * 64}")
    print(f"  {etiqueta}  ({modelo})")
    print(f"{'=' * 64}")

    # --- Latencia: la misma pregunta, varias veces.
    # Una repetición que falla no cancela el modelo: se descarta y se sigue.
    print(f"\n  Latencia — {REPETICIONES} repeticiones de la misma pregunta")
    latencias = []
    ultimo = None
    for i in range(1, REPETICIONES + 1):
        try:
            datos, segundos = pedir(PREGUNTA_LATENCIA, presupuesto)
            latencias.append(segundos)
            ultimo = datos
            print(f"    Intento {i}: {segundos:.2f} s")
        except (CuotaAgotada, PresupuestoAgotado):
            raise                          # esto corta el modelo entero, no una repetición
        except RuntimeError as error:
            print(f"    Intento {i}: descartado — {error}")
        if i < REPETICIONES:
            time.sleep(PAUSA_SEGUNDOS)

    if len(latencias) < MINIMO_MEDICIONES or ultimo is None:
        raise RuntimeError(
            f"solo {len(latencias)} de {REPETICIONES} mediciones salieron bien; "
            f"se necesitan al menos {MINIMO_MEDICIONES} para promediar"
        )

    if len(latencias) < REPETICIONES:
        print(f"    (se promedian {len(latencias)} mediciones, no {REPETICIONES})")

    promedio = statistics.mean(latencias)
    print(f"    Promedio : {promedio:.2f} s")
    print(f"    Mínimo   : {min(latencias):.2f} s")
    print(f"    Máximo   : {max(latencias):.2f} s")

    uso = ultimo["usageMetadata"]
    tokens_entrada = uso["promptTokenCount"]
    tokens_salida = uso["candidatesTokenCount"]
    costo = calcular_costo(ultimo, precio_entrada, precio_salida)

    print("\n  Costo de esa petición")
    print(f"    Tokens entrada : {tokens_entrada}")
    print(f"    Tokens salida  : {tokens_salida}")
    print(f"    Costo          : {costo:.8f} USD")
    print(f"    Proyección a {VOLUMEN_MENSUAL:,} peticiones: {costo * VOLUMEN_MENSUAL:.2f} USD/mes")

    # --- Calidad: preguntas representativas, una vez cada una
    print("\n  Calidad — respuestas a tus preguntas representativas")
    respuestas = []
    for n, pregunta in enumerate(PREGUNTAS_CALIDAD, 1):
        time.sleep(PAUSA_SEGUNDOS)
        print(f"\n    [{n}] {pregunta}")
        try:
            datos, _ = pedir(pregunta, presupuesto)
            texto = extraer_texto(datos)
            respuestas.append(texto)
            for linea in texto.strip().splitlines():
                print(f"        {linea}")
        except (CuotaAgotada, PresupuestoAgotado) as error:
            respuestas.append(None)
            print(f"        (no se preguntó — {error})")
            break                          # sin cuota, las siguientes tampoco salen
        except RuntimeError as error:
            respuestas.append(None)
            print(f"        (sin respuesta — {error})")

    # Al final, para que cuente latencia Y calidad, con sus reintentos.
    print(f"\n  Peticiones gastadas en este modelo: {presupuesto.gastadas} de {presupuesto.tope}")

    return {
        "modelo": modelo,
        "etiqueta": etiqueta,
        "entrada_por_millon": entrada_por_millon,
        "salida_por_millon": salida_por_millon,
        "latencia_promedio": promedio,
        "latencia_min": min(latencias),
        "latencia_max": max(latencias),
        "tokens_entrada": tokens_entrada,
        "tokens_salida": tokens_salida,
        "costo": costo,
        "respuestas": respuestas,
    }


def imprimir_tabla(resultados):
    """Imprime la tabla comparativa en Markdown, lista para pegar."""
    print(f"\n\n{'=' * 64}")
    print("  TABLA PARA PEGAR EN docs/decision-arquitectura.md")
    print(f"{'=' * 64}\n")

    cols = [r["etiqueta"] for r in resultados]
    print(f"Precios consultados el {FECHA_PRECIOS}.\n")
    print("| Criterio | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 1) + "|")

    def fila(nombre, valores):
        print(f"| {nombre} | " + " | ".join(valores) + " |")

    fila("Identificador del modelo", [f"`{r['modelo']}`" for r in resultados])
    fila("Costo por 1.000 tokens de entrada",
         [f"{r['entrada_por_millon'] / 1000:.6f} USD" for r in resultados])
    fila("Costo por 1.000 tokens de salida",
         [f"{r['salida_por_millon'] / 1000:.6f} USD" for r in resultados])
    fila(f"Latencia promedio ({REPETICIONES} mediciones)",
         [f"{r['latencia_promedio']:.2f} s" for r in resultados])
    fila("Latencia mínima / máxima",
         [f"{r['latencia_min']:.2f} s / {r['latencia_max']:.2f} s" for r in resultados])
    fila("Tokens de la petición medida",
         [f"{r['tokens_entrada']} entrada / {r['tokens_salida']} salida" for r in resultados])
    fila("Costo real de esa petición",
         [f"{r['costo']:.8f} USD" for r in resultados])
    fila(f"Proyección a {VOLUMEN_MENSUAL:,} peticiones/mes",
         [f"{r['costo'] * VOLUMEN_MENSUAL:.2f} USD" for r in resultados])
    fila("Calidad para mi caso", ["(completar tú)" for _ in resultados])

    if len(resultados) == 2:
        a, b = resultados
        if a["costo"] and b["costo"]:
            veces = max(a["costo"], b["costo"]) / min(a["costo"], b["costo"])
            caro = a if a["costo"] > b["costo"] else b
            print(f"\n{caro['etiqueta']} cuesta {veces:.1f}x más por petición.")
        lento = a if a["latencia_promedio"] > b["latencia_promedio"] else b
        rapido = b if lento is a else a
        dif = lento["latencia_promedio"] / rapido["latencia_promedio"]
        print(f"{lento['etiqueta']} tarda {dif:.1f}x más que {rapido['etiqueta']}.")


def main():
    """Compara los modelos y deja AI_MODEL como estaba antes de empezar.

    medir_modelo() cambia AI_MODEL para apuntar a cada modelo que mide. Sin esta
    restauración, quien llame a esta función (el menú de main.py, por ejemplo)
    quedaría usando el último modelo medido sin enterarse.
    """
    modelo_original = os.environ.get("AI_MODEL")
    try:
        _comparar()
    finally:
        # finally corre siempre: termine bien, falle, o lo cortes con Ctrl+C.
        if modelo_original is None:
            os.environ.pop("AI_MODEL", None)
        else:
            os.environ["AI_MODEL"] = modelo_original


def _comparar():
    print(f"Comparando {len(MODELOS)} modelos.")
    print(f"Precios de la página oficial, consultados el {FECHA_PRECIOS}.")

    resultados = []
    for modelo, etiqueta in MODELOS.items():
        try:
            resultados.append(medir_modelo(modelo, etiqueta))
        except CuotaAgotada as error:
            # La cuota es POR MODELO: que este se haya quedado sin cuota no
            # dice nada del siguiente, así que se sigue con él (continue, no break).
            print(f"\n  CUOTA DIARIA AGOTADA para {modelo}.")
            print(f"  {error}")
            print(f"\n  Este modelo ya usó sus {LIMITE_DIARIO_GRATUITO} peticiones de hoy.")
            continue
        except (ValueError, RuntimeError) as error:
            print(f"\n  No se pudo medir {modelo}: {error}")

    if resultados:
        imprimir_tabla(resultados)
        if len(resultados) < len(MODELOS):
            faltan = [m for m in MODELOS if m not in [r["modelo"] for r in resultados]]
            print(f"\nOJO: faltó medir {', '.join(faltan)}. Vuelve a correr el script")
            print("más tarde para completar la comparación.")
    else:
        print("\nNingún modelo se pudo medir. Revisa tu conexión y vuelve a intentar.")


if __name__ == "__main__":
    main()
