import os
import re
from dotenv import load_dotenv
from groq import Groq
from config import SYSTEM_PROMPT, MODELOS, DEFAULT_MODEL

load_dotenv()

def verificar_configuracion():
    print("🔑 Verificando configuración...")
    api_key = os.getenv("GROQ_API_KEY", "")
    if api_key.startswith("gsk_"):
        print("✅ GROQ_API_KEY: Detectada y lista.")
    else:
        print("⚠️ GROQ_API_KEY: No válida. Revisa tu archivo .env")
    print("-" * 45)

def limpiar_respuesta(texto):
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL)
    return texto.strip()

def consultar_jarvis(prompt, modelo_key="general"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "⚠️ Falta la GROQ_API_KEY en el archivo .env"
    
    try:
        client = Groq(api_key=api_key)
        modelo_nombre = MODELOS.get(modelo_key, DEFAULT_MODEL)
        print(f"📡 Consultando a {modelo_nombre}...")
        
        completion = client.chat.completions.create(
            model=modelo_nombre,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=5696
        )
        
        respuesta = completion.choices[0].message.content
        return limpiar_respuesta(respuesta)
    except Exception as e:
        return f"❌ Error: {e}"

if __name__ == "__main__":
    verificar_configuracion()
    
    print("\n🤖 Iniciando Jarvis...\n")
    
    print("--- 🧠 Prueba con Modelo General ---")
    respuesta1 = consultar_jarvis(
        "Hola Jarvis, confirma que estás en línea.",
        "general"
    )
    print(respuesta1)
    
    print("\n--- 💻 Prueba con Modelo de Código ---")
    respuesta2 = consultar_jarvis(
        "Escribe una función en Python que calcule el factorial de un número.",
        "codigo"
    )
    print(respuesta2)
    
    print("\n--- ⚡ Prueba con Modelo Rápido ---")
    respuesta3 = consultar_jarvis(
        "¿Cuánto es 15 + 27?",
        "rapido"
    )
    print(respuesta3)