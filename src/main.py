"""Miniaplicación Gemini: punto de entrada único del proyecto.

Reúne en un solo menú todo lo que se construyó por bloques:
  1. Procesar una novedad de turno con el banco de prompts   (Bloque 10)
  2. Probar la conexión y el manejo de errores               (Bloques 4 a 8)
  3. Comparar modelos por costo y latencia                   (Bloque 9)
  4. Validar la consistencia del banco de prompts            (Bloque 10)
  5. Ver la configuración actual

Uso:
    python3 src/main.py                       abre el menú
    python3 src/main.py "texto de novedad"    procesa la novedad directo, sin menú
"""

import os
import sys
from pathlib import Path

# El banco y la prueba de consistencia viven en prompts/, una carpeta al lado de
# src/. Se agrega al camino de búsqueda calculándolo desde este archivo, así
# funciona sin importar desde qué carpeta lo ejecutes.
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "prompts"))

import comparar_modelos  # noqa: E402
import consumir_gemini  # noqa: E402
import test_consistencia  # noqa: E402
from banco import BANCO_DE_PROMPTS  # noqa: E402
from consumir_gemini import (  # noqa: E402
    LIMITE_DIARIO_GRATUITO,
    PRECIOS_POR_MILLON,
    REINTENTOS,
    CuotaAgotada,
    Presupuesto,
    armar_peticion,
    calcular_costo,
    enviar_con_reintento,
    extraer_texto,
    parsear_respuesta_json,
    precios_del_modelo,
)


# ---------------------------------------------------------------------------
# Cuántas peticiones gasta cada opción
#
# Se calcula desde las constantes de cada módulo, no se escribe a mano: si
# cambias REPETICIONES en otro archivo, el menú muestra la cifra nueva solo.
# ---------------------------------------------------------------------------

def peticiones_novedad():
    """(mínimo, máximo): una por tarea, y hasta REINTENTOS por tarea si el servicio falla."""
    minimo = len(BANCO_DE_PROMPTS)
    return minimo, minimo * REINTENTOS


def peticiones_comparar():
    """(mínimo, máximo) por modelo. El máximo es el tope de presupuesto."""
    minimo = comparar_modelos.REPETICIONES + len(comparar_modelos.PREGUNTAS_CALIDAD)
    return minimo, comparar_modelos.PRESUPUESTO_POR_MODELO


def peticiones_consistencia():
    """(mínimo, máximo) del modelo activo."""
    minimo = len(BANCO_DE_PROMPTS) * test_consistencia.REPETICIONES
    return minimo, test_consistencia.PRESUPUESTO_PETICIONES


# ---------------------------------------------------------------------------
# Opción 1: procesar una novedad de turno
# ---------------------------------------------------------------------------

def aplicar_prompt(prompt, novedad, precio_entrada, precio_salida, presupuesto):
    """Aplica una tarea del banco a la novedad. Devuelve (datos, costo)."""
    url, headers, body = armar_peticion(
        novedad,
        prompt["system_instruction"],
        prompt.get("response_schema"),
    )
    # Con reintento: un 503 pasajero no hace perder la tarea.
    respuesta, _ = enviar_con_reintento(url, headers, body, REINTENTOS, presupuesto)
    texto = extraer_texto(respuesta)
    datos = parsear_respuesta_json(texto, prompt["claves_esperadas"])
    costo = calcular_costo(respuesta, precio_entrada, precio_salida)
    return datos, costo


def mostrar(datos):
    """Imprime cada clave del resultado en su propia línea."""
    for clave, valor in datos.items():
        if isinstance(valor, list):
            valor = ", ".join(valor) if valor else "(ninguno)"
        elif valor is None:
            valor = "(no indicado)"
        print(f"    {clave:<24} {valor}")


def procesar_novedad(novedad):
    """Le aplica las tres tareas del banco a una novedad."""
    if not novedad:
        print("No se ingresó ninguna novedad.")
        return

    modelo = os.getenv("AI_MODEL")
    try:
        precio_entrada, precio_salida = precios_del_modelo(modelo)
    except RuntimeError as error:
        # Se revisa antes de la primera petición: si falla acá, no se gastó cuota.
        print(f"No se puede empezar: {error}")
        return

    print(f"\nModelo: {modelo}")
    print(f"Novedad: {novedad}")

    # Lleva la cuenta de lo gastado. El tope es el máximo posible (todas las
    # tareas con todos sus reintentos), así que nunca corta: solo cuenta.
    _, maximo = peticiones_novedad()
    presupuesto = Presupuesto(maximo)
    costo_total = 0.0
    completadas = 0

    for prompt in BANCO_DE_PROMPTS:
        print(f"\n--- {prompt['nombre']} ---")
        try:
            datos, costo = aplicar_prompt(
                prompt, novedad, precio_entrada, precio_salida, presupuesto
            )
        except CuotaAgotada as error:
            # Va antes que RuntimeError porque es un caso particular de ella.
            # Sin cuota, las tareas que faltan tampoco van a salir: se corta acá.
            print(f"    CUOTA DIARIA AGOTADA: {error}")
            print(f"    El nivel gratuito permite {LIMITE_DIARIO_GRATUITO} peticiones "
                  "diarias por modelo. Las tareas que faltan no se intentan.")
            break
        except (ValueError, RuntimeError) as error:
            # Una tarea que falla no detiene a las demás.
            print(f"    No se pudo completar: {error}")
            continue

        mostrar(datos)
        costo_total += costo
        completadas += 1

        # Esto es lo que permite el JSON estructurado y no permitiría un párrafo:
        # el código decide con un "if" sobre un dato, sin interpretar texto.
        if datos.get("requiere_escalamiento") is True:
            print("    >>> AVISAR AL SUPERVISOR DE TURNO")

    print(f"\nTareas completadas: {completadas} de {len(BANCO_DE_PROMPTS)}")
    print(f"Peticiones gastadas: {presupuesto.gastadas} "
          f"(límite diario: {LIMITE_DIARIO_GRATUITO})")
    print(f"Costo total de esta novedad: {costo_total:.8f} USD")


# ---------------------------------------------------------------------------
# Opción 5: configuración actual
# ---------------------------------------------------------------------------

def mostrar_configuracion():
    modelo = os.getenv("AI_MODEL", "(no declarado)")
    print(f"\n  Modelo activo (AI_MODEL)  {modelo}")
    if modelo in PRECIOS_POR_MILLON:
        entrada, salida = PRECIOS_POR_MILLON[modelo]
        print(f"  Precio por millón         {entrada:.2f} USD entrada / {salida:.2f} USD salida")
    else:
        print("  Precio                    SIN REGISTRAR: el cálculo de costo va a fallar.")
        print("                            Agrégalo a PRECIOS_POR_MILLON en consumir_gemini.py")

    nombres = ", ".join(p["nombre"] for p in BANCO_DE_PROMPTS)
    print(f"  Prompts en el banco       {len(BANCO_DE_PROMPTS)}: {nombres}")
    print(f"  Modelos que compara la 3  {', '.join(comparar_modelos.MODELOS)}")
    print(f"  Límite nivel gratuito     {LIMITE_DIARIO_GRATUITO} peticiones diarias por modelo")


# ---------------------------------------------------------------------------
# Menú
# ---------------------------------------------------------------------------

def confirmar(mensaje):
    """Pide confirmación. Solo 's' o 'si' cuentan como sí."""
    try:
        respuesta = input(f"{mensaje} ¿Continuar? [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return respuesta in ("s", "si", "sí")


def opcion_novedad():
    try:
        novedad = input("Escribe la novedad de turno: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    procesar_novedad(novedad)


def opcion_conexion():
    consumir_gemini.demostracion()


def opcion_comparar():
    minimo, maximo = peticiones_comparar()
    modelos = len(comparar_modelos.MODELOS)
    aviso = (f"Mide {modelos} modelos y gasta entre {minimo} y {maximo} peticiones de "
             f"CADA uno (límite diario: {LIMITE_DIARIO_GRATUITO} por modelo).")
    if confirmar(aviso):
        comparar_modelos.main()


def opcion_consistencia():
    minimo, maximo = peticiones_consistencia()
    modelo = os.getenv("AI_MODEL", "(no declarado)")
    aviso = (f"Gasta entre {minimo} y {maximo} peticiones de {modelo} "
             f"(límite diario: {LIMITE_DIARIO_GRATUITO}).")
    if confirmar(aviso):
        test_consistencia.main()


def construir_opciones():
    """Arma el menú con el costo en peticiones de cada opción."""
    n_min, n_max = peticiones_novedad()
    c_min, c_max = peticiones_comparar()
    t_min, t_max = peticiones_consistencia()
    entradas = [
        ("Procesar una novedad de turno", f"{n_min} a {n_max} peticiones",
         opcion_novedad),
        ("Probar conexión y manejo de errores", "1 petición",
         opcion_conexion),
        ("Comparar modelos: costo y latencia", f"{c_min} a {c_max} por modelo",
         opcion_comparar),
        ("Validar consistencia del banco", f"{t_min} a {t_max} peticiones",
         opcion_consistencia),
        ("Ver la configuración actual", "sin peticiones",
         mostrar_configuracion),
    ]
    # :<36 rellena el nombre con espacios hasta 36 caracteres: así el costo
    # queda alineado en columna para todas las opciones.
    return {
        str(numero): (f"{nombre:<36} ({costo})", accion)
        for numero, (nombre, costo, accion) in enumerate(entradas, 1)
    }


def menu():
    opciones = construir_opciones()
    while True:
        modelo = os.getenv("AI_MODEL", "(no declarado)")
        print("\n" + "=" * 62)
        print("  MINIAPLICACIÓN GEMINI — Novedades de turno")
        print("=" * 62)
        print(f"  Modelo activo: {modelo}\n")
        for clave, (texto, _) in opciones.items():
            print(f"  {clave}. {texto}")
        print("  0. Salir")

        try:
            eleccion = input("\nElige una opción: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return

        if eleccion == "0":
            print("Hasta luego.")
            return
        if eleccion not in opciones:
            print("Opción no válida.")
            continue

        _, accion = opciones[eleccion]
        try:
            accion()
        except KeyboardInterrupt:
            # Ctrl+C a mitad de una opción larga vuelve al menú, no rompe el programa.
            print("\nOperación cancelada.")

        try:
            input("\nPresiona Enter para volver al menú...")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return


def main():
    if len(sys.argv) > 1:
        # Con texto en la línea de comandos se procesa directo, sin menú.
        procesar_novedad(" ".join(sys.argv[1:]).strip())
    else:
        menu()


if __name__ == "__main__":
    main()
