"""Prueba la consistencia del banco de prompts contra la API real.

Ejecuta cada prompt varias veces con el mismo ejemplo y cuenta cuántas veces
la respuesta llegó como JSON válido y con las claves esperadas.
Guarda el resultado en prompts/registro_resultados.json.

Uso:
    python3 prompts/test_consistencia.py
"""

import json
import os
import sys
import time
from datetime import datetime

# consumir_gemini.py está en src/, una carpeta al lado de esta. Se agrega al
# camino de búsqueda para poder importarlo desde acá.
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))

from banco import BANCO_DE_PROMPTS  # noqa: E402
from consumir_gemini import PAUSA_SEGUNDOS, obtener_respuesta_json  # noqa: E402

REPETICIONES = 3            # el mínimo que pide la actividad
ARCHIVO_SALIDA = os.path.join(AQUI, "registro_resultados.json")


def probar_prompt(prompt):
    """Repite un prompt y devuelve cuántas de sus respuestas fueron válidas."""
    print(f"\n--- {prompt['nombre']} ---")
    validos = 0
    invalidos = 0       # la API respondió, pero no con el JSON pedido: es el prompt
    errores = 0         # la API no respondió (red, 503, cuota): no dice nada del prompt
    fallos = []

    for intento in range(1, REPETICIONES + 1):
        try:
            resultado, _ = obtener_respuesta_json(
                prompt["ejemplo_usuario"],
                prompt["system_instruction"],
                prompt["claves_esperadas"],
            )
            validos += 1
            print(f"  intento {intento}: válido   -> {json.dumps(resultado, ensure_ascii=False)}")
        except ValueError as error:
            invalidos += 1
            fallos.append(f"intento {intento}: {error}")
            print(f"  intento {intento}: INVÁLIDO -> {error}")
        except RuntimeError as error:
            errores += 1
            fallos.append(f"intento {intento}: {error}")
            print(f"  intento {intento}: ERROR    -> {error}")
        time.sleep(PAUSA_SEGUNDOS)

    # La tasa se calcula solo sobre las respuestas que llegaron: un corte del
    # servicio no debe contar como una falla del prompt.
    medidos = validos + invalidos
    tasa = round(validos / medidos, 2) if medidos else None

    print(f"  resultado: {validos}/{medidos} respuestas válidas", end="")
    print(f" ({errores} sin respuesta del servicio)" if errores else "")

    return {
        "validos": validos,
        "invalidos": invalidos,
        "errores_del_servicio": errores,
        "repeticiones": REPETICIONES,
        "tasa_consistencia": tasa,
        "fallos": fallos,
    }


def main():
    modelo = os.getenv("AI_MODEL")
    print(f"Banco: {len(BANCO_DE_PROMPTS)} prompts, {REPETICIONES} repeticiones cada uno.")
    print(f"Modelo: {modelo}")

    registro = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "modelo": modelo,
        "repeticiones_por_prompt": REPETICIONES,
        "prompts": {},
    }
    for prompt in BANCO_DE_PROMPTS:
        registro["prompts"][prompt["nombre"]] = probar_prompt(prompt)

    # --- Resumen
    print("\n=== RESUMEN ===")
    total_validos = 0
    total_medidos = 0
    total_errores = 0
    for nombre, datos in registro["prompts"].items():
        if datos["invalidos"] > 0:
            estado = "REVISAR"      # el prompt falló: hay que ajustarlo
        elif datos["errores_del_servicio"] > 0:
            estado = "REPETIR"      # el servicio falló: volver a correr más tarde
        else:
            estado = "OK"
        medidos = datos["validos"] + datos["invalidos"]
        print(f"  [{estado:>7}] {nombre}: {datos['validos']}/{medidos}")
        total_validos += datos["validos"]
        total_medidos += medidos
        total_errores += datos["errores_del_servicio"]

    registro["tasa_global"] = round(total_validos / total_medidos, 2) if total_medidos else None
    if total_medidos:
        print(f"\n  Global: {total_validos}/{total_medidos} ({registro['tasa_global']:.0%})")
    else:
        print("\n  Global: no llegó ninguna respuesta, no se pudo medir.")
    if total_errores:
        print(f"  {total_errores} intento(s) sin respuesta del servicio. No cuentan contra los")
        print("  prompts; repite la prueba más tarde para completarlos.")

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as archivo:
        json.dump(registro, archivo, indent=2, ensure_ascii=False)
    print(f"  Registro guardado en {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    main()
