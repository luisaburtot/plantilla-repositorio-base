"""Módulo común de la miniaplicación: todo lo que habla con la API de Gemini.

Lo usan main.py, comparar_modelos.py y prompts/test_consistencia.py. Cualquier
pieza que necesiten dos o más de ellos vive acá, una sola vez: los precios, el
límite de cuota, los reintentos y el manejo de errores.
"""

import json
import os
import re
import time

import requests
from dotenv import load_dotenv

# Lee el archivo .env y deja sus variables disponibles para os.getenv()
load_dotenv()

# Precios por MILLÓN de tokens (entrada, salida), de la página oficial:
# https://ai.google.dev/gemini-api/docs/pricing
FECHA_PRECIOS = "22-10-2026"
#
# Van en una tabla por modelo, no en dos constantes sueltas, para que el costo
# siempre corresponda al modelo declarado en AI_MODEL. Si cambias de modelo en
# el .env y no está acá, el cálculo falla con un mensaje claro en vez de
# reportar un costo equivocado sin avisar.
PRECIOS_POR_MILLON = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.8-flash": (0.75, 3.75),   # se duplica desde el 01-01-2027
}


def precios_del_modelo(modelo):
    """Devuelve (precio_entrada, precio_salida) POR TOKEN para el modelo dado."""
    if not modelo:
        # Sin esto, a quien le falta AI_MODEL le aparecería "no hay precio para
        # el modelo 'None'", que no le dice qué tiene que arreglar.
        raise RuntimeError("Falta declarar la variable AI_MODEL en el archivo .env")
    if modelo not in PRECIOS_POR_MILLON:
        raise RuntimeError(
            f"No hay precio registrado para el modelo '{modelo}'. "
            "Agrégalo a PRECIOS_POR_MILLON con los valores de la página oficial."
        )
    entrada, salida = PRECIOS_POR_MILLON[modelo]
    return entrada / 1_000_000, salida / 1_000_000


def armar_peticion(pregunta, system_instruction=None, response_schema=None):
    """Devuelve (url, headers, body) listos para enviar a Gemini.

    system_instruction: instrucción de comportamiento, en un canal separado de
        la pregunta. Opcional.
    response_schema: forma exacta que debe cumplir el JSON de respuesta.
        Opcional. Si se entrega, la API genera bajo esa restricción.
    """
    if not pregunta:
        raise ValueError("La pregunta no puede estar vacía")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta declarar la variable GEMINI_API_KEY en el archivo .env")

    modelo = os.getenv("AI_MODEL")
    if not modelo:
        raise RuntimeError("Falta declarar la variable AI_MODEL en el archivo .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}

    # Lo que cambia en cada llamada: la pregunta del usuario.
    body = {"contents": [{"parts": [{"text": pregunta}]}]}

    # Lo que NO cambia: la instrucción de comportamiento. Canal aparte.
    # OJO: la clave JSON es "systemInstruction" (camelCase), no "system_instruction".
    # Escribirla con guion bajo da un error 400 "Unknown name".
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    # Restricción estructural de la salida, cuando se pide.
    if response_schema is not None:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }

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


# ---------------------------------------------------------------------------
# Reintentos y cuota
#
# Antes cada script tenía su propia copia de todo esto. Ahora vive una sola vez
# acá, y main.py, comparar_modelos.py y test_consistencia.py lo importan.
# ---------------------------------------------------------------------------

# El nivel gratuito permite 20 peticiones diarias POR MODELO, y cada reintento
# cuenta como una petición más.
LIMITE_DIARIO_GRATUITO = 20

REINTENTOS = 3        # intentos por petición ante fallas transitorias
PAUSA_SEGUNDOS = 3    # separación entre peticiones seguidas, para no gatillar el 429

# Fallas que se arreglan solas esperando: servidor saturado o caído, límite de
# ritmo y cortes de red. Las demás (400, 401, 403, 404) no se arreglan
# esperando, así que no se reintentan.
CODIGOS_TRANSITORIOS = ("429", "500", "502", "503", "504")
MENSAJES_TRANSITORIOS = ("No se pudo conectar", "tardó demasiado", "Falló la petición")


class CuotaAgotada(RuntimeError):
    """La cuota diaria del nivel gratuito se acabó: no sirve seguir hoy."""


class PresupuestoAgotado(RuntimeError):
    """Se alcanzó el tope de peticiones que un script se permite gastar."""


class Presupuesto:
    """Lleva la cuenta de las peticiones que un script se permite gastar.

    Cada script crea el suyo con el tope que necesita. Así ninguno depende de un
    contador global que haya que acordarse de reiniciar.
    """

    def __init__(self, tope):
        self.tope = tope
        self.gastadas = 0

    def gastar(self):
        """Descuenta una petición, o falla si ya no quedan."""
        if self.gastadas >= self.tope:
            raise PresupuestoAgotado(
                f"se alcanzó el tope de {self.tope} peticiones "
                f"(límite diario del nivel gratuito: {LIMITE_DIARIO_GRATUITO})"
            )
        self.gastadas += 1


def es_cuota_diaria(error):
    """Distingue el 429 de cuota diaria agotada del 429 de ritmo.

    El de ritmo se arregla esperando segundos; el de cuota diaria, solo horas.
    """
    texto = str(error).lower()
    return "429" in texto and "quota" in texto


def es_transitorio(error):
    """Decide si vale la pena reintentar esta falla."""
    texto = str(error)
    if any(codigo in texto for codigo in CODIGOS_TRANSITORIOS):
        return True
    return any(marca in texto for marca in MENSAJES_TRANSITORIOS)


def enviar_con_reintento(url, headers, body, intentos=REINTENTOS, presupuesto=None):
    """Envía la petición, reintentando ante fallas transitorias.

    Devuelve (datos, segundos): segundos es lo que tardó el intento que salió
    bien, sin contar las esperas entre reintentos. Así sirve también para medir
    latencia.

    Si la cuota diaria se agotó lanza CuotaAgotada de inmediato, sin reintentar:
    esperar segundos no la repone. Si se entrega un presupuesto, cada intento
    descuenta de él.
    """
    espera = 2
    for intento in range(1, intentos + 1):
        if presupuesto is not None:
            presupuesto.gastar()
        inicio = time.perf_counter()
        try:
            datos = enviar_peticion(url, headers, body)
        except RuntimeError as error:
            if es_cuota_diaria(error):
                raise CuotaAgotada(str(error)) from error
            if not es_transitorio(error) or intento == intentos:
                raise          # 400, 401, 404, o se acabaron los intentos
            print(f"      falla transitoria ({error})")
            print(f"      espero {espera}s y reintento ({intento}/{intentos - 1})...")
            time.sleep(espera)
            espera *= 2        # backoff exponencial: 2, 4, 8 segundos
            continue
        return datos, time.perf_counter() - inicio


def extraer_texto(datos):
    """Saca el texto generado del diccionario de respuesta."""
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(
            "La respuesta no trae el texto generado en el lugar esperado."
        ) from error


def parsear_respuesta_json(texto, claves_esperadas=None):
    """Convierte el texto del modelo en un diccionario de Python.

    Limpia el bloque de markdown si viene envuelto, valida que sea JSON, que sea
    un objeto, y que traiga las claves que se esperaban.
    """
    texto_limpio = texto.strip()
    # Quita ```json o ``` al principio, y ``` al final. Las expresiones regulares
    # toleran que venga con la palabra "json" o sin ella, y espacios alrededor.
    texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)
    texto_limpio = re.sub(r"\s*```$", "", texto_limpio)

    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError as error:
        raise ValueError("La respuesta del modelo no es JSON válido.") from error

    # json.loads("5") devuelve un int, y json.loads("[1,2]") una lista: los dos
    # son JSON válido pero no sirven para buscar claves. Sin esta comprobación,
    # el "in" de más abajo revienta con TypeError en vez de ValueError.
    if not isinstance(datos, dict):
        raise ValueError(
            f"La respuesta es JSON válido pero no es un objeto (llegó {type(datos).__name__})."
        )

    if claves_esperadas:
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


def obtener_dato_de_prueba(pregunta):
    """Llama a las funciones anteriores en orden y devuelve (texto, costo)."""
    url, headers, body = armar_peticion(pregunta)
    # Los precios se resuelven ANTES de enviar: si el modelo no tiene precio
    # registrado, falla sin haber gastado una petición de la cuota.
    precio_entrada, precio_salida = precios_del_modelo(os.getenv("AI_MODEL"))
    datos = enviar_peticion(url, headers, body)
    texto = extraer_texto(datos)
    costo = calcular_costo(datos, precio_entrada, precio_salida)
    return texto, costo


# ---------------------------------------------------------------------------
# Demostración del manejo de errores
#
# Está dentro de una función para que main.py pueda llamarla desde su menú.
# Al final del archivo, el if __name__ == "__main__": la ejecuta solo cuando
# corres este archivo directamente, y así importar el módulo no dispara
# peticiones a la API.
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
