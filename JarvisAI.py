import os
import re
from dotenv import load_dotenv
from groq import Groq
from config import SYSTEM_PROMPT, MODELOS
from tools import buscar_en_web

load_dotenv()


def limpiar_respuesta(texto: str) -> str:
    """Elimina las etiquetas internas <think> de los modelos de razonamiento."""
    return re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()


def iniciar_chat_interactivo():
    """Inicia el chat interactivo autónomo con Jarvis."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not api_key.startswith("gsk_"):
        print("❌ GROQ_API_KEY no válida. Revisa tu archivo .env")
        return
    
    client = Groq(api_key=api_key)
    historial = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    print("=" * 60)
    print("🤖 JARVIS - Asistente Personal (Búsqueda Autónoma)")
    print("=" * 60)
    print("💡 Escribe normalmente. Jarvis buscará en Google si lo necesita.")
    print("   Escribe 'salir' para terminar.")
    print("=" * 60)
    
    while True:
        try:
            usuario_input = input("\n👤 Tú: ").strip()
            
            if not usuario_input:
                continue
            
            if usuario_input.lower() in ["salir", "exit", "quit"]:
                print("\n🤖 Jarvis: ¡Hasta luego!")
                break
            
            historial.append({"role": "user", "content": usuario_input})
            
            # PASO 1: Jarvis evalúa si responder directo o generar [BUSCAR: ...]
            response = client.chat.completions.create(
                model=MODELOS["general"],
                messages=historial,
                temperature=0.7
            )
            
            respuesta_bruta = response.choices[0].message.content
            respuesta_limpia = limpiar_respuesta(respuesta_bruta)
            
            # PASO 2: Verificar si Jarvis decidió solicitar una búsqueda
            buscar_match = re.search(r'\[BUSCAR:\s*(.*?)\]', respuesta_limpia, re.IGNORECASE)
            
            if buscar_match:
                query = buscar_match.group(1).strip()
                print(f"\n🌐 Consultando a Google via tools.py: '{query}'...")
                
                # Ejecutar búsqueda en tools.py
                resultados_web = buscar_en_web(query)
                
                # Prompt con contexto para el modelo
                prompt_con_web = (
                    f"[INFORMACIÓN OBTENIDA DE GOOGLE PARA '{query}']:\n"
                    f"{resultados_web}\n\n"
                    f"Responde a la pregunta del usuario utilizando la información anterior."
                )
                
                # Crear copia del historial con los datos de internet para la síntesis
                historial_temporal = historial + [{"role": "user", "content": prompt_con_web}]
                
                # PASO 3: Respuesta final sintetizada
                response_final = client.chat.completions.create(
                    model=MODELOS["general"],
                    messages=historial_temporal,
                    temperature=0.7
                )
                
                respuesta_final = limpiar_respuesta(response_final.choices[0].message.content)
                
                # Guardar respuesta final en el historial real
                historial.append({"role": "assistant", "content": respuesta_final})
                print(f"\n🤖 Jarvis: {respuesta_final}")
            else:
                # Respuesta directa si no hizo falta buscar
                historial.append({"role": "assistant", "content": respuesta_limpia})
                print(f"\n🤖 Jarvis: {respuesta_limpia}")
            
        except KeyboardInterrupt:
            print("\n\n🤖 Jarvis: Sesión interrumpida.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            if len(historial) > 1 and historial[-1]["role"] == "user":
                historial.pop()


if __name__ == "__main__":
    iniciar_chat_interactivo()