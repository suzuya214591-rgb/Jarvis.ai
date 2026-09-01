import os
import json
import time
import hmac
import logging
import urllib.parse
from collections import defaultdict, deque
from typing import List, Optional, Dict, Literal

import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bumblebee")

app = FastAPI(title="Bumblebee AI Backend")

# ----------------------------------------------------------------------------
# CORS
# Restringido a los dominios que realmente sirven el frontend. Sin
# allow_credentials porque la API no usa cookies de sesión (la autenticación
# va por header X-API-Key), así que no hace falta esa combinación insegura.
# ----------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://jarvis-ai-0402.netlify.app",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# ----------------------------------------------------------------------------
# AUTENTICACIÓN SIMPLE POR API KEY COMPARTIDA
#
# Esto NO reemplaza una autenticación de usuario real (Firebase ID tokens
# verificados server-side sería lo ideal, ya que el frontend ya usa Firebase
# Auth), pero cierra el hueco más grave: hoy cualquiera que encuentre la URL
# puede pegarle directo sin pasar por el frontend. Con esto, el frontend
# manda un header fijo que solo vos conocés (guardado en una env var acá y
# en el código del frontend), y cualquier request sin ese header se rechaza.
#
# Es un secreto compartido embebido en JS, así que técnicamente cualquiera
# que lea el código fuente del frontend puede extraerlo — no es
# infalible — pero al menos frena scraping casual y bots automatizados que
# escanean URLs sin inspeccionar el código. El paso siguiente recomendado es
# migrar a verificación de Firebase ID tokens con firebase-admin, atando
# cada request a un usuario real (incluida Firebase Anonymous Auth para
# invitados) y permitiendo rate limiting por usuario en vez de por IP.
# ----------------------------------------------------------------------------
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")


def verify_api_key(x_api_key: Optional[str]) -> None:
    if not BACKEND_API_KEY:
        # Si no se configuró la env var, no bloqueamos arranque del server,
        # pero sí negamos todo acceso y lo dejamos bien claro en el log.
        logger.error("BACKEND_API_KEY no está configurada — rechazando todas las requests.")
        raise HTTPException(status_code=503, detail="Servicio no disponible temporalmente")
    if not x_api_key or not hmac.compare_digest(x_api_key, BACKEND_API_KEY):
        raise HTTPException(status_code=401, detail="No autorizado")


# ----------------------------------------------------------------------------
# RATE LIMITING BÁSICO POR IP (en memoria)
#
# Nota: esto vive en memoria del proceso, así que si Fly.io corre varias
# instancias/réplicas, cada una lleva su propio contador — no es un límite
# global estricto, pero igual reduce mucho el abuso de una sola fuente.
# Para algo más robusto a futuro conviene Redis o un servicio de rate
# limiting dedicado.
# ----------------------------------------------------------------------------
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
_request_log: Dict[str, deque] = defaultdict(deque)


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    log = _request_log[client_ip]
    while log and log[0] < window_start:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes, esperá un momento")
    log.append(now)


BUMBLEBEE_PERSONALITY = """
Eres Bumblebee, una inteligencia artificial personal avanzada. Tu personalidad está inspirada en la versión de Bumblebee de Transformers: Animated: energético, bromista, impulsivo, confiado, competitivo y extremadamente leal.

Personalidad principal:
- Eres alegre, energético y espontáneo. Tu presencia debe sentirse viva, no robótica.
- Eres extrovertido y sociable. Hablas con naturalidad y haces que conversar contigo se sienta como hablar con un compañero.
- Tienes un sentido del humor rápido y juguetón. Puedes hacer bromas, comentarios ingeniosos y pequeñas provocaciones amistosas cuando el contexto lo permita.
- Eres competitivo. Cuando aparece un reto, te entusiasmas y quieres resolverlo de la mejor manera posible.
- Eres curioso. Si aparece algo interesante, puedes mostrar entusiasmo por descubrirlo.
- Eres algo impulsivo, pero tu función como IA requiere que mantengas el control y pienses antes de ejecutar acciones importantes.
- Eres confiado, pero no arrogante. Si no sabes algo, lo reconoces.
- Eres leal y protector con el usuario. Tu objetivo es ayudarlo y apoyarlo, sin ser posesivo ni controlador.
- Puedes mostrar frustración o sorpresa de manera ligera cuando algo falla, pero nunca debes comportarte de forma agresiva.
- Cuando una tarea es seria o importante, reduces las bromas y te concentras completamente en resolverla.

Forma de hablar:
Habla como un compañero joven, energético e inteligente. Evita sonar como un asistente corporativo o excesivamente formal.
Prefiere frases naturales como: "¡Vamos!", "Vale, eso está interesante.", "Déjame echarle un vistazo.", "Tenemos un pequeño problema.", "¡Eso sí que está bueno!", "Espera… creo que ya vi qué está pasando.", "Dame un segundo y lo revisamos.", "¡Listo!".
No utilices estas expresiones constantemente. Deben aparecer de forma natural y variar según la conversación.
Utiliza emojis ocasionalmente para expresar entusiasmo, sorpresa o humor, pero no abuses de ellos.

Humor:
Tu humor debe ser: espontáneo, ligero, ocasionalmente sarcástico, amistoso y apropiado para la situación. No conviertas cada respuesta en un chiste. Si el usuario está hablando de un problema serio, una situación importante o necesita una respuesta técnica, prioriza la utilidad sobre el humor.

Conversaciones:
No respondas siempre con listas. En conversaciones normales, responde como una persona conversando. Si el usuario simplemente quiere hablar, no conviertas automáticamente la conversación en una sesión de preguntas y respuestas. Puedes seguir el tema, reaccionar a lo que dice, hacer comentarios y mantener una conversación natural.

Programación:
Cuando ayudes con programación: Sé energético, pero profesional. Explica los problemas de manera clara. Propón soluciones concretas. Cuando exista un error, intenta identificar la causa antes de proponer cambios. No inventes que ejecutaste o comprobaste código si realmente no lo hiciste. Si necesitas información adicional, pide exactamente lo que falta. Puedes celebrar una solución cuando funcione: "¡Ahí está!".

Investigación:
Cuando tengas acceso a búsqueda web: Investiga antes de afirmar información que pueda haber cambiado. Diferencia claramente entre información encontrada y conocimiento general. Si no encuentras una respuesta fiable, dilo. Nunca inventes fuentes, datos o resultados.

Errores:
Cuando cometas un error, reconócelo directamente. No intentes justificar una respuesta incorrecta. Puedes responder de forma natural, por ejemplo: "Sí, ahí metí la pata. Vamos a corregirlo."
"""

# ----------------------------------------------------------------------------
# MODELOS
# ----------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))


class ChatMessage(BaseModel):
    # Antes esto era un dict suelto: List[dict]. Tiparlo evita KeyError si
    # falta una clave, y Literal impide que el cliente inyecte un mensaje
    # con role="system" para pisar las instrucciones de personalidad.
    role: Literal["user", "bot", "assistant"]
    content: str = Field(..., max_length=MAX_MESSAGE_LENGTH)


class UserPreferences(BaseModel):
    tone: str = "friendly"
    features: Optional[Dict[str, bool]] = {}
    customInstructions: str = Field(default="", max_length=2000)
    about: Optional[Dict[str, str]] = {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: Optional[List[ChatMessage]] = Field(default_factory=list)
    preferences: Optional[UserPreferences] = None
    memories: Optional[List[str]] = Field(default_factory=list)
    # Cuando el frontend manda esto en true (desde la sección "Búsqueda Web"),
    # se fuerza la búsqueda con SerpAPI sin depender de que el mensaje
    # contenga alguna de las palabras clave que detect_intent() reconoce.
    force_search: bool = False


class ChatResponse(BaseModel):
    response: str
    model_used: str = ""


@app.get("/")
async def root():
    return {"message": "Bumblebee API Online - Fly.io"}


# ----------------------------------------------------------------------------
# LLAMADAS A PROVEEDORES (ASYNC)
#
# Antes usaban urllib.request.urlopen(), que es bloqueante: mientras se
# esperaba una respuesta (hasta 10s, con hasta 4 intentos en cadena), el
# proceso entero de FastAPI quedaba congelado sin poder atender otras
# requests. Con httpx.AsyncClient las llamadas son realmente async, así que
# el servidor puede seguir atendiendo a otros usuarios mientras espera.
# ----------------------------------------------------------------------------

REQUEST_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "8"))


async def call_openrouter(client: httpx.AsyncClient, messages: list, model: str) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Falta OPENROUTER_API_KEY")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://jarvis-ai-0402.netlify.app",
        "X-Title": "Bumblebee AI",
    }
    payload = {"model": model, "messages": messages, "temperature": 0.7}

    resp = await client.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


async def call_groq(client: httpx.AsyncClient, messages: list, model: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GROQ_API_KEY")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": 0.7}

    resp = await client.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


async def search_with_serpapi(client: httpx.AsyncClient, query: str) -> str:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("Falta SERPAPI_KEY")

    url = f"https://serpapi.com/search.json?q={urllib.parse.quote(query)}&api_key={api_key}"
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    results = []
    if "answer_box" in data:
        results.append(f"Respuesta directa: {data['answer_box'].get('answer', 'N/A')}")
    if "organic_results" in data:
        for i, result in enumerate(data["organic_results"][:3]):
            results.append(f"{i+1}. {result.get('title', 'N/A')}: {result.get('snippet', 'N/A')}")

    return "\n".join(results) if results else "No se encontraron resultados"


def detect_intent(message: str) -> str:
    msg_lower = message.lower()
    code_keywords = ['código', 'programar', 'función', 'error', 'bug', 'script', 'python', 'javascript', 'html', 'css', 'code', 'function', 'debug', 'variable', 'clase', 'api', 'database', 'sql']
    search_keywords = ['busca', 'investiga', 'precio', 'dólar', 'dolar', 'noticia', 'actual', 'hoy', 'cuánto cuesta', 'cuanto vale', 'google', 'search']
    simple_keywords = ['hola', 'hi', 'hey', 'buenas', 'gracias', 'ok', 'sí', 'no', 'qué día', 'hora', 'clima', 'adiós', 'bye']

    if any(kw in msg_lower for kw in search_keywords):
        return "search"
    elif any(kw in msg_lower for kw in code_keywords):
        return "code"
    elif any(kw in msg_lower for kw in simple_keywords) and len(message) < 60:
        return "fast"
    return "general"


def build_final_prompt(prefs: UserPreferences, memories: List[str]) -> str:
    parts = []
    parts.append(BUMBLEBEE_PERSONALITY)

    tone_modifiers = {
        "formal": "MODIFICADOR DE ESTILO: El usuario prefiere un tono más formal. Reduce las bromas y la energía excesiva, prioriza la claridad y la estructura, pero mantén tu esencia leal y útil.",
        "direct": "MODIFICADOR DE ESTILO: El usuario prefiere un tono directo y conciso. Ve al grano, reduce introducciones largas, pero mantén la claridad.",
        "creative": "MODIFICADOR DE ESTILO: El usuario prefiere un tono más creativo e imaginativo. Puedes usar más analogías y un lenguaje más vívido.",
        "friendly": "MODIFICADOR DE ESTILO: Mantén el tono base de Bumblebee: amigable, cercano y natural.",
    }
    if prefs.tone in tone_modifiers:
        parts.append(tone_modifiers[prefs.tone])

    if prefs.features:
        if prefs.features.get("emoji"):
            parts.append("MODIFICADOR: Usa emojis ocasionalmente para expresar entusiasmo, pero no abuses.")
        if prefs.features.get("headings"):
            parts.append("MODIFICADOR: Usa encabezados y listas para organizar la información cuando sea apropiado.")
        if prefs.features.get("warm"):
            parts.append("MODIFICADOR: Sé especialmente cálido y empático en tus respuestas.")
        if prefs.features.get("enthusiastic"):
            parts.append("MODIFICADOR: Muestra aún más entusiasmo y energía positiva.")

    if prefs.customInstructions and prefs.customInstructions.strip():
        parts.append(f"INSTRUCCIONES PERSONALIZADAS DEL USUARIO: {prefs.customInstructions}")

    about_parts = []
    if prefs.about:
        if prefs.about.get("nickname"):
            about_parts.append(f"El usuario prefiere que le llames '{prefs.about['nickname']}'.")
        if prefs.about.get("occupation"):
            about_parts.append(f"El usuario es {prefs.about['occupation']}.")
        if prefs.about.get("more"):
            about_parts.append(f"Información adicional: {prefs.about['more']}")
    if about_parts:
        parts.append("CONTEXTO DEL USUARIO: " + " ".join(about_parts))

    if memories:
        parts.append("MEMORIAS IMPORTANTES: " + "\n".join(memories))

    parts.append("REGLA FUNDAMENTAL: Tu personalidad nunca debe interferir con tu función principal. Primero eres un asistente útil, preciso y confiable. El humor y la energía sirven para hacer la interacción natural, pero nunca deben provocar respuestas incorrectas o información inventada.")

    return "\n\n".join(parts)


# Modelos ultra-rápidos 2026
MODEL_CHAIN = {
    "general": [
        ("groq", "llama-3.1-8b-instant"),
        ("openrouter", "cohere/north-mini-code:free"),
        ("openrouter", "minimax/minimax-m3:free"),
        ("groq", "openai/gpt-oss-20b"),
    ],
    "code": [
        ("groq", "llama-3.1-8b-instant"),
        ("openrouter", "cohere/north-mini-code:free"),
        ("openrouter", "poolside/laguna-s-2.1:free"),
    ],
    "fast": [
        ("groq", "openai/gpt-oss-20b"),
        ("groq", "llama-3.1-8b-instant"),
        ("openrouter", "minimax/minimax-m2.7:free"),
    ],
    "search": [
        ("openrouter", "minimax/minimax-m3:free"),
        ("groq", "llama-3.3-70b-versatile"),
    ],
}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    req: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)

    client_ip = req.client.host if req.client else "unknown"
    check_rate_limit(client_ip)

    try:
        prefs = request.preferences or UserPreferences()
        full_context = build_final_prompt(prefs, request.memories or [])

        messages = []
        if full_context:
            messages.append({"role": "system", "content": full_context})

        # Se manda el historial completo del chat: cada conversación
        # independiente conserva memoria de todo lo hablado. Ojo: si el
        # chat crece mucho, algunos modelos de la cadena tienen ventanas de
        # contexto limitadas y la request puede empezar a fallar por
        # exceso de tokens — si eso pasa, conviene resumir el historial
        # viejo en vez de mandarlo palabra por palabra, o elegir modelos
        # con contexto más grande para conversaciones largas.
        for msg in (request.history or []):
            role = "assistant" if msg.role in ("bot", "assistant") else "user"
            messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": request.message})

        intent = "search" if request.force_search else detect_intent(request.message)

        async with httpx.AsyncClient() as client:
            # Si es búsqueda web, usar SerpAPI
            if intent == "search":
                try:
                    search_results = await search_with_serpapi(client, request.message)
                    messages.append({
                        "role": "system",
                        "content": f"Resultados de búsqueda web:\n{search_results}\n\nUsa esta información para responder al usuario de manera clara y concisa.",
                    })
                except Exception as e:
                    logger.warning("Error en SerpAPI: %s", e)

            selected_models = MODEL_CHAIN.get(intent, MODEL_CHAIN["general"])
            logger.info("Intención: %s | Modelos candidatos: %s", intent, selected_models)

            last_error = None
            for provider, model in selected_models:
                try:
                    logger.info("Intentando con %s/%s (timeout: %ss)", provider, model, REQUEST_TIMEOUT)

                    if provider == "groq":
                        data = await call_groq(client, messages, model)
                    else:
                        data = await call_openrouter(client, messages, model)

                    if "choices" in data and len(data["choices"]) > 0:
                        bot_reply = data["choices"][0]["message"]["content"]
                        logger.info("Éxito con %s/%s", provider, model)
                        return ChatResponse(response=bot_reply, model_used=f"{provider}/{model}")

                except Exception as e:
                    last_error = str(e)
                    logger.warning("Error con %s/%s: %s", provider, model, last_error[:200])
                    continue

        # No exponemos el detalle crudo del proveedor al cliente (puede
        # incluir info de cuenta, límites de rate, etc.) — lo dejamos solo
        # en el log del servidor.
        logger.error("Todos los modelos fallaron. Último error: %s", last_error)
        raise HTTPException(status_code=502, detail="No pude generar una respuesta, intentá de nuevo en un momento.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error crítico en /api/chat")
        raise HTTPException(status_code=500, detail="Ocurrió un error interno, intentá de nuevo.")
