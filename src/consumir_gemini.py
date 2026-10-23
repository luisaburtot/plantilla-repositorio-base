"""Módulo que habla con la API de Gemini.

Lo usan main.py, comparar_modelos.py y prompts/test_consistencia.py.
Las funciones van en el orden en que se usan: armar la petición, enviarla,
sacar el texto de la respuesta y calcular lo que costó.
"""

import json
import os
import requests
from dotenv import load_dotenv

# Lee el archivo .env y deja sus variables disponibles para os.getenv()
load_dotenv()

# Precios por MILLON de tokens (entrada, salida), de la página oficial:
# https://ai.google.dev/gemini-api/docs/pricing  (consultados el 22-10-2026)
PRECIOS_POR_MILLON = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.8-flash": (0.75, 3.75),
}

# Espera entre peticiones seguidas, para no pasarse del ritmo que permite la API.
PAUSA_SEGUNDOS = 3


def precios_del_modelo(modelo):
    """Devuelve (precio_entrada, precio_salida) POR TOKEN del modelo indicado."""
    if not modelo:
        raise RuntimeError("Falta declarar la variable AI_MODEL en el archivo .env")
    if modelo not in PRECIOS_POR_MILLON:
        raise RuntimeError(f"No hay precio registrado para el modelo '{modelo}'")
    entrada, salida = PRECIOS_POR_MILLON[modelo]
    return entrada / 1_000_000, salida / 1_000_000


def armar_peticion(pregunta, system_instruction=None, pedir_json=False, modelo=None):
    """Devuelve (url, headers, body) listos para enviar a Gemini.

    system_instruction: instrucción de comportamiento, separada de la pregunta.
    pedir_json: True para que la API responda solo con JSON, sin texto alrededor.
    modelo: si no se indica, se usa el del archivo .env.
    """
    if not pregunta:
        raise ValueError("La pregunta no puede estar vacía")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta declarar la variable GEMINI_API_KEY en el archivo .env")

    if modelo is None:
        modelo = os.getenv("AI_MODEL")
    if not modelo:
        raise RuntimeError("Falta declarar la variable AI_MODEL en el archivo .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}

    # La instrucción de sistema va en su propio campo, no mezclada con la pregunta.
    # OJO: la clave es "systemInstruction" (camelCase); con guion bajo da error 400.
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    if pedir_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    return url, headers, body


def enviar_peticion(url, headers, body):
    """Hace el POST y devuelve la respuesta ya convertida a diccionario."""
    # 1) Problemas de red: no hay respuesta del servidor
    try:
        respuesta = requests.post(url, json=body, headers=headers, timeout=(5, 60))
    except requests.exceptions.Timeout as error:
        raise RuntimeError("El servicio tardó demasiado en responder.") from error
    except requests.exceptions.ConnectionError as error:
        raise RuntimeError(
            "No se pudo conectar con el servicio. Intenta de nuevo en unos segundos."
        ) from error
    except requests.exceptions.RequestException as error:
        raise RuntimeError(f"Falló la petición al servicio: {error}") from error

    # 2) Hubo respuesta, pero puede no ser JSON (una página de error, por ejemplo)
    try:
        datos = respuesta.json()
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError(
            "La respuesta del servicio no llegó en el formato esperado."
        ) from error

    # 3) Es JSON válido, pero el servidor avisa un error (404, 429, 503...)
    if respuesta.status_code != 200:
        detalle = "sin detalle"
        if isinstance(datos, dict):
            detalle = datos.get("error", {}).get("message", detalle)
        raise RuntimeError(
            f"El servicio respondió con error {respuesta.status_code}: {detalle}"
        )

    return datos


def extraer_texto(datos):
    """Saca el texto generado del diccionario de respuesta."""
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(
            "La respuesta no trae el texto generado en el lugar esperado."
        ) from error


def parsear_respuesta_json(texto, claves_esperadas):
    """Convierte el texto del modelo en un diccionario y revisa que traiga las claves."""
    # A veces el modelo envuelve el JSON en un bloque de markdown: se le quita.
    texto_limpio = texto.replace("```json", "").replace("```", "").strip()

    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError as error:
        raise ValueError("La respuesta del modelo no es JSON válido.") from error

    if not isinstance(datos, dict):
        raise ValueError("La respuesta es JSON válido pero no es un objeto con claves.")

    faltan = [clave for clave in claves_esperadas if clave not in datos]
    if faltan:
        raise ValueError(f"Faltan claves en la respuesta: {', '.join(faltan)}")

    return datos


def calcular_costo(datos, precio_entrada, precio_salida):
    """Calcula el costo de la petición leyendo usageMetadata de la respuesta."""
    try:
        uso = datos["usageMetadata"]
        tokens_entrada = uso["promptTokenCount"]
        tokens_salida = uso["candidatesTokenCount"]
    except (KeyError, TypeError) as error:
        raise RuntimeError(
            "La respuesta no trae el conteo de tokens en el lugar esperado."
        ) from error

    return (tokens_entrada * precio_entrada) + (tokens_salida * precio_salida)


def obtener_dato_de_prueba(pregunta, system_instruction=None, pedir_json=False, modelo=None):
    """Llama a las funciones anteriores en orden y devuelve (texto, costo)."""
    if modelo is None:
        modelo = os.getenv("AI_MODEL")
    # Los precios se buscan ANTES de enviar: si el modelo no tiene precio
    # registrado, falla sin haber gastado una petición.
    precio_entrada, precio_salida = precios_del_modelo(modelo)
    url, headers, body = armar_peticion(pregunta, system_instruction, pedir_json, modelo)
    datos = enviar_peticion(url, headers, body)
    texto = extraer_texto(datos)
    costo = calcular_costo(datos, precio_entrada, precio_salida)
    return texto, costo


def obtener_respuesta_json(pregunta, system_instruction, claves_esperadas):
    """Como obtener_dato_de_prueba, pero convierte la respuesta a diccionario.

    Es lo que usa el banco de prompts. Devuelve (diccionario, costo).
    """
    texto, costo = obtener_dato_de_prueba(pregunta, system_instruction, pedir_json=True)
    return parsear_respuesta_json(texto, claves_esperadas), costo


# ---------------------------------------------------------------------------
# Demostración del manejo de errores
#
# Está dentro de una función para que main.py pueda llamarla desde su menú.
# El if __name__ == "__main__" del final la ejecuta solo cuando corres este
# archivo directamente: importar el módulo no dispara peticiones a la API.
# ---------------------------------------------------------------------------
def demostracion():
    """Corre los cuatro casos de manejo de errores. Gasta 1 petición real."""

    # Caso 1: la pregunta viene vacía. No llega a la API: falla en armar_peticion.
    print("--- Entrada vacía ---")
    try:
        texto, costo = obtener_dato_de_prueba("")
        print(texto)
        print(f"Costo: {costo:.6f} USD")
    except (ValueError, RuntimeError) as error:
        print(f"No se pudo completar la operación: {error}")

    print()

    # Caso 2: pregunta válida. Esta es la única llamada real a la API.
    print("--- Entrada válida ---")
    try:
        texto, costo = obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona")
        print(texto)
        print(f"Costo: {costo:.6f} USD")
    except (ValueError, RuntimeError) as error:
        print(f"No se pudo completar la operación: {error}")

    print()

    # Caso 3: respuesta con una forma distinta a la esperada.
    # Se le pasa el diccionario a mano para no depender de que la API falle.
    print("--- Respuesta inesperada ---")
    try:
        print(extraer_texto({"candidates": []}))
    except (ValueError, RuntimeError) as error:
        print(f"No se pudo completar la operación: {error}")

    print()

    # Caso 4: el cálculo de costo con los números del ejemplo de la lección.
    # No hace falta una petición real: se arma el diccionario a mano.
    print("--- Cálculo de costo (datos de ejemplo) ---")
    datos_ejemplo = {
        "usageMetadata": {
            "promptTokenCount": 850,
            "candidatesTokenCount": 320,
            "totalTokenCount": 1170,
        }
    }
    try:
        costo_ejemplo = calcular_costo(datos_ejemplo, 0.00000010, 0.00000040)
        print(f"Sin redondear: {costo_ejemplo}")
        print(f"Redondeado:    {costo_ejemplo:.6f} USD")
    except (ValueError, RuntimeError) as error:
        print(f"No se pudo completar la operación: {error}")


if __name__ == "__main__":
    demostracion()
