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
THANK_YOU_FILE = Path("app/templates/thank_you.html")


@app.on_event("startup")
def startup_event():
    init_db()


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

from .functions import execute_register_user

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db=Depends(get_db_session)):

    conv_id = req.conversation_id
    history = conversations.setdefault(conv_id, [])

    # Añadir mensaje del usuario al historial
    history.append({"role": "user", "content": req.message})

    # Obtener respuesta del agente
    raw_response = run_tourbot(history)
    output = raw_response.output[0]

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
    
            history.append({"role": "assistant", "content": reply})
    
            return ChatResponse(
                conversation_id=conv_id,
                reply=reply,
                stage="completed",
                registration_completed=True,
                wait_listed=result.get("wait_listed", False),
                suggested_tours=[],
            )


    # --- 2. SI ES RESPUESTA DE TEXTO ---
    if output.type == "message":
        reply = output.content[0].text

        # Guardar respuesta del bot
        history.append({"role": "assistant", "content": reply})

        return ChatResponse(
            conversation_id=conv_id,
            reply=reply,
            stage="chat",
            registration_completed=False,
            wait_listed=False,
            suggested_tours=[],
        )
