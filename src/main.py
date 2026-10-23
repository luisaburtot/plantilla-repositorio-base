"""Miniaplicación Gemini: punto de entrada único del proyecto.

Reúne en un solo menú todo lo que se construyó por bloques:
  1. Analizar una opinión de cliente con el banco de prompts   (Bloque 10)
  2. Probar la conexión y el manejo de errores                 (Bloques 4 a 8)
  3. Comparar dos modelos por costo y latencia                 (Bloque 9)
  4. Validar la consistencia del banco de prompts              (Bloque 10)
  5. Ver la configuración actual

Uso:
    python3 src/main.py
"""

import os
import sys

# El banco y su prueba están en prompts/, una carpeta al lado de src/. Se agrega
# al camino de búsqueda para poder importarlos desde acá.
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "prompts"))

import comparar_modelos  # noqa: E402
import consumir_gemini  # noqa: E402
import test_consistencia  # noqa: E402
from banco import BANCO_DE_PROMPTS  # noqa: E402
from consumir_gemini import (  # noqa: E402
    PRECIOS_POR_MILLON,
    obtener_respuesta_json,
    precios_del_modelo,
)


# ---------------------------------------------------------------------------
# Opción 1: analizar una opinión con el banco de prompts
# ---------------------------------------------------------------------------

def analizar_opinion(opinion):
    """Le aplica las tres tareas del banco a una opinión escrita por el usuario."""
    if not opinion:
        print("No se escribió ninguna opinión.")
        return

    # Se revisa el modelo una sola vez, antes de la primera petición.
    try:
        precios_del_modelo(os.getenv("AI_MODEL"))
    except RuntimeError as error:
        print(f"No se puede empezar: {error}")
        return

    costo_total = 0
    for prompt in BANCO_DE_PROMPTS:
        print(f"\n--- {prompt['nombre']} ---")
        try:
            resultado, costo = obtener_respuesta_json(
                opinion, prompt["system_instruction"], prompt["claves_esperadas"]
            )
        except (ValueError, RuntimeError) as error:
            print(f"    No se pudo completar: {error}")
            continue        # una tarea que falla no detiene a las demás

        for clave, valor in resultado.items():
            print(f"    {clave}: {valor}")
        costo_total += costo

    print(f"\nCosto total de este análisis: {costo_total:.8f} USD")


# ---------------------------------------------------------------------------
# Opción 5: configuración actual
# ---------------------------------------------------------------------------

def mostrar_configuracion():
    modelo = os.getenv("AI_MODEL")
    print(f"\n  Modelo activo (AI_MODEL): {modelo}")
    if modelo in PRECIOS_POR_MILLON:
        entrada, salida = PRECIOS_POR_MILLON[modelo]
        print(f"  Precio por millón de tokens: {entrada:.2f} USD entrada / {salida:.2f} USD salida")
    else:
        print("  Precio: SIN REGISTRAR. Agrégalo a PRECIOS_POR_MILLON en consumir_gemini.py")
    print(f"  Prompts en el banco: {len(BANCO_DE_PROMPTS)}")
    for prompt in BANCO_DE_PROMPTS:
        print(f"    - {prompt['nombre']}")
    print(f"  Modelos que compara la opción 3: {', '.join(comparar_modelos.MODELOS)}")
    print("  Cuota del nivel gratuito: un máximo diario por modelo, que se consulta en")
    print("  https://aistudio.google.com/rate-limit")


# ---------------------------------------------------------------------------
# Menú
# ---------------------------------------------------------------------------

def confirmar(mensaje):
    """Pregunta antes de una opción que gasta varias peticiones. Solo 's' cuenta como sí."""
    respuesta = input(f"{mensaje} ¿Continuar? [s/N]: ").strip().lower()
    return respuesta == "s"


def menu():
    # Cuántas peticiones gasta cada opción. Se calcula desde las constantes de
    # cada módulo, para que el menú siga diciendo la verdad si alguna cambia.
    gasto_analizar = len(BANCO_DE_PROMPTS)
    gasto_comparar = comparar_modelos.REPETICIONES
    gasto_consistencia = len(BANCO_DE_PROMPTS) * test_consistencia.REPETICIONES

    while True:
        print("\n" + "=" * 60)
        print("  MINIAPLICACIÓN GEMINI")
        print("=" * 60)
        print(f"  Modelo activo: {os.getenv('AI_MODEL')}\n")
        print(f"  1. Analizar una opinión de cliente        ({gasto_analizar} peticiones)")
        print("  2. Probar conexión y manejo de errores    (1 petición)")
        print(f"  3. Comparar modelos: costo y latencia     ({gasto_comparar} por modelo)")
        print(f"  4. Validar consistencia del banco         ({gasto_consistencia} peticiones)")
        print("  5. Ver la configuración actual            (sin peticiones)")
        print("  0. Salir")

        opcion = input("\nElige una opción: ").strip()

        if opcion == "1":
            opinion = input("Escribe la opinión del cliente: ").strip()
            analizar_opinion(opinion)
        elif opcion == "2":
            consumir_gemini.demostracion()
        elif opcion == "3":
            if confirmar(f"Gasta {gasto_comparar} peticiones de CADA modelo."):
                comparar_modelos.main()
        elif opcion == "4":
            if confirmar(f"Gasta {gasto_consistencia} peticiones del modelo activo."):
                test_consistencia.main()
        elif opcion == "5":
            mostrar_configuracion()
        elif opcion == "0":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    try:
        menu()
    except (KeyboardInterrupt, EOFError):   # Ctrl+C o Ctrl+D: se sale sin mostrar un error
        print("\nHasta luego.")
