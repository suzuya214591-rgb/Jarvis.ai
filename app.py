import os
import re
import base64
import traceback
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from config import SYSTEM_PROMPT, MODELOS
from tools import buscar_en_web

load_dotenv()

# --- DICCIONARIO DE ESPECIALIDADES ---
ESPECIALIDADES = {
    "🤖 Jarvis (General)": SYSTEM_PROMPT,
    
    "📈 Trading Pro": """Eres un analista financiero senior y trader profesional especializado en:
- Análisis técnico avanzado (Price Action, SMC, ICT)
- Lectura de gráficos y patrones de velas
- Identificación de order blocks, FVG y zonas de liquidez
- Gestión de riesgo y cálculo de posición
- Noticias macroeconómicas y su impacto en mercados

Proporciona siempre: niveles clave, entry, SL, TP y ratio riesgo/beneficio.""",

    "💻 Developer Expert": """Eres un desarrollador Full-Stack senior y arquitecto de software.
Especialidades:
- Python, JavaScript, React, Node.js
- Clean Code, patrones de diseño, mejores prácticas
- Debugging y optimización de código
- Explicaciones claras y estructuradas
- Ejemplos prácticos y funcionales""",

    "📄 OCR & Documentos": """Eres un especialista en extracción y análisis de información de documentos.
- Extrae texto de imágenes con precisión
- Resume contenido de manera estructurada
- Organiza datos en tablas o viñetas
- Detecta información clave (fechas, montos, nombres)""",

    "✍️ Copywriter Pro": """Eres un experto en redacción publicitaria y creación de contenido.
- Copywriting persuasivo y profesional
- SEO y optimización de textos
- Generación de ideas creativas
- Tono adaptable (formal, casual, técnico)
- Corrección de estilo y gramática"""
}

# --- CONFIGURACIÓN ---
st.set_page_config(
    page_title="Jarvis AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    /* Fondo principal */
    .stApp {
        background-color: #0a0a0a !important;
        color: #e0e0e0 !important;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #000000 !important;
        border-right: 1px solid #1a1a1a !important;
    }
    
    /* Ocultar elementos de Streamlit */
    header[data-testid="stHeader"] { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Burbuja del usuario (derecha, verde) */
    div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
        flex-direction: row-reverse !important;
    }
    
    div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] {
        background-color: #10b981 !important;
        color: #ffffff !important;
        padding: 12px 20px !important;
        border-radius: 18px !important;
        display: inline-block !important;
    }

    /* Burbuja del asistente (izquierda, gris oscuro) */
    div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] {
        background-color: #1f1f1f !important;
        color: #e0e0e0 !important;
        padding: 12px 20px !important;
        border-radius: 18px !important;
    }

    /* Input de chat */
    .stChatInput > div {
        background-color: #1a1a1a !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 24px !important;
    }
    
    .stChatInput textarea {
        color: #ffffff !important;
    }

    /* Botones */
    .stButton > button {
        background-color: transparent !important;
        color: #e0e0e0 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        width: 100%;
        text-align: left !important;
        padding: 10px 14px !important;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background-color: #1a1a1a !important;
        border-color: #404040 !important;
    }
    
    /* Disclaimer */
    .disclaimer {
        font-size: 0.75rem;
        color: #666666;
        text-align: center;
        margin-top: 10px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def limpiar_respuesta(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r'\[BUSCAR:.*?\]', '', texto, flags=re.IGNORECASE)
    return texto.strip()

def codificar_imagen_a_base64(imagen_bytes) -> str:
    return base64.b64encode(imagen_bytes).decode('utf-8')

@st.cache_resource
def obtener_cliente_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("❌ GROQ_API_KEY no configurada en .env")
        st.stop()
    return Groq(api_key=api_key)

client = obtener_cliente_groq()

# --- ESTADO ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "imagen_subida" not in st.session_state:
    st.session_state.imagen_subida = None

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🤖 **Jarvis AI**")
    
    if st.button("📝 Nuevo chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.imagen_subida = None
        st.rerun()

    st.markdown("---")
    st.markdown("**🎯 Especialidad**")
    especialidad = st.selectbox(
        "Selecciona modo:",
        options=list(ESPECIALIDADES.keys()),
        label_visibility="collapsed"
    )
    prompt_sistema = ESPECIALIDADES[especialidad]

    st.markdown("---")
    uploaded_file = st.file_uploader(
        "📎 Adjuntar imagen",
        type=["png", "jpg", "jpeg"],
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        st.session_state.imagen_subida = uploaded_file
        st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    st.markdown("---")
    st.markdown("**🕒 Recientes**")
    st.caption("• Análisis de gráfico EUR/USD")
    st.caption("• Código Python para API")
    st.caption("• Redactar email profesional")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("👤 **Usuario** \n<span style='color:#666; font-size:11px;'>Plan Gratuito</span>", unsafe_allow_html=True)

# --- CHAT ---
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if "imagen" in msg and msg["imagen"]:
            st.image(msg["imagen"], width=250)
        st.markdown(msg["content"])

# --- INPUT ---
if prompt := st.chat_input("Escribe tu mensaje para Jarvis..."):
    
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "imagen": st.session_state.imagen_subida
    })
    
    with st.chat_message("user", avatar="👤"):
        if st.session_state.imagen_subida:
            st.image(st.session_state.imagen_subida, width=250)
        st.markdown(prompt)

    # Contexto con sistema
    historial = [{"role": "system", "content": prompt_sistema}]
    for m in st.session_state.messages:
        historial.append({"role": m["role"], "content": m["content"]})

    with st.chat_message("assistant", avatar="🤖"):
        try:
            # CON IMAGEN
            if st.session_state.imagen_subida:
                with st.spinner("👁️ Analizando imagen..."):
                    image_bytes = st.session_state.imagen_subida.getvalue()
                    image_b64 = codificar_imagen_a_base64(image_bytes)
                    
                    response = client.chat.completions.create(
                        model=MODELOS["codigo"],
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                            ]}
                        ],
                        temperature=0.3,
                        max_tokens=4096
                    )
                    
                    respuesta = limpiar_respuesta(response.choices[0].message.content)
                    st.markdown(respuesta)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": respuesta,
                        "imagen": st.session_state.imagen_subida
                    })

            # SIN IMAGEN - TEXTO NORMAL
            else:
                with st.spinner("🤔 Pensando..."):
                    response = client.chat.completions.create(
                        model=MODELOS["general"],
                        messages=historial,
                        temperature=0.5
                    )
                    
                    respuesta = limpiar_respuesta(response.choices[0].message.content)
                    
                    # Si detecta necesidad de búsqueda
                    buscar_match = re.search(r'\[BUSCAR:\s*(.*?)\]', respuesta, re.IGNORECASE)
                    if buscar_match:
                        query = buscar_match.group(1).strip()
                        with st.spinner(f"🌐 Buscando: {query}..."):
                            resultados = buscar_en_web(query)
                            
                            prompt_web = f"Usa esta información para responder:\n{resultados}\n\nPregunta: {prompt}"
                            historial_web = historial + [{"role": "user", "content": prompt_web}]
                            
                            response_final = client.chat.completions.create(
                                model=MODELOS["general"],
                                messages=historial_web,
                                temperature=0.5
                            )
                            
                            respuesta_final = limpiar_respuesta(response_final.choices[0].message.content)
                            st.markdown(respuesta_final)
                            st.session_state.messages.append({"role": "assistant", "content": respuesta_final})
                    else:
                        st.markdown(respuesta)
                        st.session_state.messages.append({"role": "assistant", "content": respuesta})

        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.code(traceback.format_exc())

# --- DISCLAIMER ---
st.markdown("<p class='disclaimer'>Jarvis AI puede cometer errores. Verifica la información importante.</p>", unsafe_allow_html=True)