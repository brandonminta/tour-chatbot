"""FastAPI entry point for the Montebello TourBot."""
from __future__ import annotations

from uuid import uuid4
from typing import Dict, List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from pathlib import Path
from .schemas import ChatRequest, ChatResponse, InitChatResponse
from .database import init_db, list_active_tours, get_db_session
from .tourbot_agent import run_tourbot

# ------------------------------------------
# Conversación en memoria
# ------------------------------------------

# Estructura:
#   conversations[conversation_id] = [
#        {"role": "user", "content": "..."},
#        {"role": "assistant", "content": "..."},
#   ]
conversations: Dict[str, List[Dict[str, str]]] = {}

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


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


# ------------------------------------------
# Inicializar nueva conversación
# ------------------------------------------

@app.get("/chat/init", response_model=InitChatResponse)
def init_chat(db=Depends(get_db_session)):
    conv_id = str(uuid4())

    # Crear historial vacío
    conversations[conv_id] = []

    # Obtener fechas activas (solo para mostrar al usuario)
    tours = list_active_tours(db)
    suggestions = [
        f"{i+1}. {t.date.strftime('%d/%m/%Y')} · Cupo inmediato · grupos de {t.capacity} familias"
        for i, t in enumerate(tours)
    ]

    # Mensaje inicial (generado por el agente)
    system_intro = (
        "Hola 👋 soy SAM, tu asistente de Admisiones del Colegio Montebello. "
        "Estoy aquí para ayudarte a resolver dudas y, si deseas, reservar un cupo en nuestro Tour Informativo. "
        "Para comenzar, ¿cómo te gustaría que te llame?"
    )

    # Guardar como respuesta inicial del bot
    conversations[conv_id].append({"role": "assistant", "content": system_intro})

    return InitChatResponse(
        conversation_id=conv_id,
        reply=system_intro,
        stage="chat",               # Ya NO hay etapas rígidas
        suggested_tours=suggestions
    )


# ------------------------------------------
# Recibir mensaje del usuario
# ------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db=Depends(get_db_session)):

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # Crear conversa si no existe
    conv_id = req.conversation_id
    if conv_id not in conversations:
        conversations[conv_id] = []

    history = conversations[conv_id]

    # Agregar mensaje del usuario al historial
    history.append({"role": "user", "content": req.message})

    # Obtener respuesta del agente TourBot
    bot_reply = run_tourbot(history)

    # Guardar respuesta en historial
    history.append({"role": "assistant", "content": bot_reply})

    # Obtener tours sugeridos (solo informativo)
    tours = list_active_tours(db)
    suggestions = [
        f"{i+1}. {t.date.strftime('%d/%m/%Y')} · Cupo inmediato · grupos de {t.capacity} familias"
        for i, t in enumerate(tours)
    ]

    return ChatResponse(
        conversation_id=conv_id,
        reply=bot_reply,
        stage="chat",               # No usamos etapas
        registration_completed=False,
        wait_listed=False,
        suggested_tours=suggestions
    )
