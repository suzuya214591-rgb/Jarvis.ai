import os
from serpapi import GoogleSearch

def buscar_en_web(query: str) -> str:
    """Realiza una búsqueda en Google mediante SerpApi y retorna los resultados enriquecidos."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return "⚠️ No hay clave SERPAPI_KEY configurada en el archivo .env"
    
    try:
        search = GoogleSearch({
            "q": query,
            "hl": "es",
            "gl": "es",
            "num": 5,
            "api_key": api_key
        })
        results = search.get_dict()
        
        if "organic_results" not in results or len(results["organic_results"]) == 0:
            return f"⚠️ No se encontraron resultados para: '{query}'"
        
        respuesta = f"Resultados de Google para '{query}':\n"
        for result in results["organic_results"][:5]:
            titulo = result.get('title', 'Sin título')
            snippet = result.get('snippet', '')
            respuesta += f"- {titulo}: {snippet}\n"
        
        return respuesta
    except Exception as e:
        return f"❌ Error en búsqueda web: {e}"