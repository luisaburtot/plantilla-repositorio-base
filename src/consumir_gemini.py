
import os   
import requests
from dotenv import load_dotenv

load_dotenv()

def armar_peticion(pregunta):
    "Devuelve (url, headers, body) listos para enviar a Gemini."
    if not pregunta:
        raise ValueError("La pregunta no puede estar vacía")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta o declarar la variable GEMINI_API_KEY en el archivo .env")

    modelo = os.getenv("AI_MODEL")
    if not modelo:
        raise RuntimeError("Falta o declarar la variable AI_MODEL en el archivo .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, headers, body


def enviar_peticion(url, headers, body):
    "POST y devuelve la respuesta ya convertida a diccionario."
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

    try:
        datos = respuesta.json()
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError(
            "La respuesta del servicio no llegó en el formato esperado."
        ) from error

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


def obtener_dato_de_prueba(pregunta):
    url, headers, body = armar_peticion(pregunta)
    datos = enviar_peticion(url, headers, body)
    return extraer_texto(datos)


print("--- Entrada válida ---")
try:
    print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))
except (ValueError, RuntimeError) as error:
    print(f"No se pudo completar la operación: {error}")


