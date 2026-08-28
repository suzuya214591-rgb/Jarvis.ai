import os
import json
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

api_key = os.getenv("SERPAPI_KEY")

if not api_key:
    print("❌ Error: No se encontró SERPAPI_KEY en el archivo .env")
else:
    print(f"🔑 Usando API Key que empieza con: {api_key[:10]}...")

    # Búsqueda de prueba simple
    search = GoogleSearch({
        "q": "precio del bitcoin",
        "hl": "es",
        "gl": "es",
        "num": 3,
        "api_key": api_key
    })

    try:
        print("⏳ Consultando a SerpApi...")
        results = search.get_dict()
        
        print("\n" + "="*50)
        print("RESPUESTA CRUDA DEL SERVIDOR:")
        print(json.dumps(results, indent=2))
        print("="*50 + "\n")
        
        if "organic_results" in results:
            print("✅ ¡ÉXITO! La búsqueda funciona perfectamente.")
        elif "error" in results:
            print(f"❌ ERROR DE SERPAPI: {results['error']}")
        else:
            print("⚠️ No hubo error, pero tampoco devolvió 'organic_results'.")
            
    except Exception as e:
        print(f"❌ Error de conexión en Python: {e}")