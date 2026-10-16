from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
modelo = os.getenv("AI_MODEL")

print(f"GEMINI_API_KEY: {'cargada (' + str(len(api_key)) + ' chars)' if api_key else 'NO ENCONTRADA'}")
print(f"AI_MODEL: {modelo or 'NO ENCONTRADO'}")
