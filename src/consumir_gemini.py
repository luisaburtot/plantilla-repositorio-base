import os
import requests
from dotenv import load_dotenv

load_dotenv()


def obtener_dato_de_prueba(pregunta):
    api_key = os.getenv("GEMINI_API_KEY")
    modelo = os.getenv("AI_MODEL")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está definida en el .env")
    if not modelo:
        raise RuntimeError("AI_MODEL no está definida en el .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}

    respuesta = requests.post(url, json=body, headers=headers, timeout=30)

    if respuesta.status_code != 200:
        raise RuntimeError(f"HTTP {respuesta.status_code}: {respuesta.text}")

    datos = respuesta.json()
    return datos["candidates"][0]["content"]["parts"][0]["text"]


print(obtener_dato_de_prueba("Hola, ¿cómo estás?"))