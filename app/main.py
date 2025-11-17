"""FastAPI entry point for the Montebello TourBot."""
from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass, field
from typing import Dict, List

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from pathlib import Path
from .schemas import ChatRequest, ChatResponse, InitChatResponse
from .database import init_db, list_active_tours, get_db_session
from .tourbot_agent import run_tourbot
from .state_manager import extract_state

# ------------------------------------------
# Conversación en memoria
# ------------------------------------------

# Estructura:
@dataclass
class ConversationThread:
    """Almacena historial y resumen comprimido para ahorrar tokens."""

    history: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""

    MAX_MESSAGES: int = 14
    RECENT_MESSAGES: int = 10

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self._trim()

    def _trim(self) -> None:
        if len(self.history) <= self.MAX_MESSAGES:
            return

        state = extract_state(self.history)
        snapshot = (
            f"Nombre: {state.get('name') or 'sin nombre'}, "
            f"Email: {state.get('email') or 'no indicado'}, "
            f"Teléfono: {state.get('phone') or 'no indicado'}, "
            f"Grado: {state.get('grade') or 'no indicado'}, "
            f"Intención: {state.get('intent')}, "
            f"Listo para registro: {'sí' if state.get('ready_for_registration') else 'no'}"
        )

        self.summary = " | ".join(filter(None, [self.summary, snapshot])).strip(" |")
        self.history = self.history[-self.RECENT_MESSAGES :]


conversations: Dict[str, ConversationThread] = {}

# ------------------------------------------
# FastAPI
# ------------------------------------------

app = FastAPI(title="SAM - Montebello TourBot", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
INDEX_FILE = Path("app/templates/index.html")
THANK_YOU_FILE = Path("app/templates/thank_you.html")


@app.on_event("startup")
def startup_event():
    init_db()


def _build_tour_suggestions(db) -> List[str]:
    tours = list_active_tours(db)
    return [
        f"{i+1}. {t.date.strftime('%d/%m/%Y')} · Cupo inmediato · grupos de {t.capacity} familias"
        for i, t in enumerate(tours)
    ]


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/gracias", response_class=HTMLResponse)
def thank_you():
    return HTMLResponse(THANK_YOU_FILE.read_text(encoding="utf-8"))


# ------------------------------------------
# Inicializar nueva conversación
# ------------------------------------------

@app.get("/chat/init", response_model=InitChatResponse)
def init_chat(db=Depends(get_db_session)):
    conv_id = str(uuid4())

    # Crear historial vacío
    conversations[conv_id] = ConversationThread()

    # Obtener fechas activas (solo para mostrar al usuario)
    suggestions = _build_tour_suggestions(db)

    # Mensaje inicial (generado por el agente)
    system_intro = (
        "Hola 👋 soy SAM, tu asistente de Admisiones del Colegio Montebello. "
        "Estoy aquí para ayudarte a resolver dudas y, si deseas, reservar un cupo en nuestro Tour Informativo. "
        "Para comenzar, ¿cómo te gustaría que te llame?"
    )

    # Guardar como respuesta inicial del bot
    conversations[conv_id].append("assistant", system_intro)

    return InitChatResponse(
        conversation_id=conv_id,
        reply=system_intro,
        stage="chat",               # Ya NO hay etapas rígidas
        suggested_tours=suggestions
    )


# ------------------------------------------
# Recibir mensaje del usuario
# ------------------------------------------

from .functions import execute_register_user

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db=Depends(get_db_session)):

    conv_id = req.conversation_id or str(uuid4())
    conversation = conversations.setdefault(conv_id, ConversationThread())

    # Añadir mensaje del usuario al historial
    conversation.append("user", req.message)

    # Obtener respuesta del agente
    raw_response = run_tourbot(conversation.history, conversation.summary)
    output = raw_response.output[0]

    suggestions = _build_tour_suggestions(db)

    # --- 1. SI ES UNA LLAMADA A FUNCIÓN ---
    # --- Si es llamada a función ---
    if output.type == "function_call":
        fn_name = output.name
    
        # IMPORTANTE: convertir el string JSON a dict
        import json
        args = json.loads(output.arguments)
    
        if fn_name == "register_user":
            result = execute_register_user(db, args)
    
            reply = (
                "¡Listo! Tu registro ha sido procesado 😊 "
                "En breve recibirás una confirmación por correo."
            )
    
            conversation.append("assistant", reply)
    
            return ChatResponse(
                conversation_id=conv_id,
                reply=reply,
                stage="completed",
                registration_completed=True,
                wait_listed=result.get("wait_listed", False),
                suggested_tours=suggestions,
            )


    # --- 2. SI ES RESPUESTA DE TEXTO ---
    if output.type == "message":
        reply = output.content[0].text

        # Guardar respuesta del bot
        conversation.append("assistant", reply)

        return ChatResponse(
            conversation_id=conv_id,
            reply=reply,
            stage="chat",
            registration_completed=False,
            wait_listed=False,
            suggested_tours=suggestions,
        )
