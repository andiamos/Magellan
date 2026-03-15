import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Get the key from .env or ask for it
api_key = os.getenv("GEMINI_API_KEY") or input("Introdu Cheia API Gemini: ")

genai.configure(api_key=api_key)

print("--- Modele Disponibile pe acest API Key ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name} (Display: {m.display_name})")
except Exception as e:
    print(f"Eroare la listarea modelelor: {e}")
