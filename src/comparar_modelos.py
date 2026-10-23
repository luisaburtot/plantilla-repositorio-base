"""Compara dos modelos de Gemini midiendo latencia y costo reales.

Le hace la misma pregunta a cada modelo varias veces, mide cuánto tarda cada
respuesta y calcula su costo con los precios de consumir_gemini.py.

Uso: python3 src/comparar_modelos.py
"""

import time

from consumir_gemini import PAUSA_SEGUNDOS, obtener_dato_de_prueba, precios_del_modelo

MODELOS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]
PREGUNTA = "Explica en dos frases qué es un token en un modelo de lenguaje."
REPETICIONES = 3            # mediciones de latencia por modelo
VOLUMEN_MENSUAL = 50_000    # peticiones al mes que supone la lección, para proyectar


def medir_modelo(modelo):
    """Mide un modelo. Devuelve un diccionario con su latencia promedio y su costo."""
    print(f"\n=== {modelo} ===")
    precios_del_modelo(modelo)      # falla antes de gastar peticiones si no tiene precio

    tiempos = []
    for intento in range(1, REPETICIONES + 1):
        inicio = time.time()
        try:
            texto, costo = obtener_dato_de_prueba(PREGUNTA, modelo=modelo)
            segundos = time.time() - inicio
            tiempos.append(segundos)
            print(f"  Intento {intento}: {segundos:.2f} s")
        except RuntimeError as error:
            # Una medición que falla se descarta; las demás siguen.
            print(f"  Intento {intento}: descartado ({error})")
        time.sleep(PAUSA_SEGUNDOS)

    if not tiempos:
        raise RuntimeError("ninguna de las mediciones salió bien")

    promedio = sum(tiempos) / len(tiempos)
    print(f"  Latencia promedio: {promedio:.2f} s ({len(tiempos)} mediciones)")
    print(f"  Costo de la última petición: {costo:.8f} USD")
    print(f"  Última respuesta: {texto.strip()}")

    return {"modelo": modelo, "latencia": promedio, "costo": costo}


def imprimir_tabla(resultados):
    """Imprime la comparación en formato Markdown, lista para pegar en docs/."""
    nombres = [r["modelo"] for r in resultados]
    print("\n| Criterio | " + " | ".join(nombres) + " |")
    print("|---" * (len(nombres) + 1) + "|")

    latencias = [f"{r['latencia']:.2f} s" for r in resultados]
    print("| Latencia promedio | " + " | ".join(latencias) + " |")

    costos = [f"{r['costo']:.8f} USD" for r in resultados]
    print("| Costo de una petición | " + " | ".join(costos) + " |")

    proyeccion = [f"{r['costo'] * VOLUMEN_MENSUAL:.2f} USD" for r in resultados]
    print(f"| Proyección a {VOLUMEN_MENSUAL:,} peticiones/mes | " + " | ".join(proyeccion) + " |")


def main():
    resultados = []
    for modelo in MODELOS:
        # Si un modelo falla (sin cuota, sin precio, caído), se avisa y se sigue con el otro.
        try:
            resultados.append(medir_modelo(modelo))
        except (ValueError, RuntimeError) as error:
            print(f"  No se pudo medir {modelo}: {error}")

    if resultados:
        imprimir_tabla(resultados)


if __name__ == "__main__":
    main()
