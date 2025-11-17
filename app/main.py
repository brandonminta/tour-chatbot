
from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass, field
from typing import Dict, List, Any
import json

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from pathlib import Path

from .schemas import ChatRequest, ChatResponse, InitChatResponse
from .database import init_db, list_active_tours, list_courses, get_db_session
from .tourbot_agent import run_tourbot
from .state_manager import extract_state
from .functions import execute_register_user


# ============================================================
# Conversation memory
# ============================================================

@dataclass
class ConversationThread:
    """Stores chat history and compressed summary for token savings."""

    history: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""

    MAX_MESSAGES: int = 10
    RECENT_MESSAGES: int = 6

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self._trim()

    def _trim(self) -> None:
        # If history exceeds threshold, compress it using semantic extraction
        if len(self.history) <= self.MAX_MESSAGES:
            return

        # Only extract state every 3 messages to reduce token usage
        if len(self.history) % 3 == 0:
            state = extract_state(self.history)
        else:
            state = {}

        # Build short snapshot
        grades = state.get("grades") or []
        if isinstance(grades, str):
            grades = [g.strip() for g in grades.split(",") if g.strip()]

        snapshot = (
            f"Nombre: {state.get('name') or '-'}, "
            f"Email: {state.get('email') or '-'}, "
            f"Teléfono: {state.get('phone') or '-'}, "
            f"Grados: {', '.join(grades) or '-'}, "
            f"Intención: {state.get('intent') or '-'}, "
            f"Listo: {'sí' if state.get('ready_for_registration') else 'no'}"
        )

        # Overwrite summary (do NOT accumulate)
        self.summary = snapshot

        # Keep only last few messages
        self.history = self.history[-self.RECENT_MESSAGES:]


conversations: Dict[str, ConversationThread] = {}


# ============================================================
# FastAPI setup
# ============================================================

app = FastAPI(title="SAM - Montebello TourBot", version="3.0")

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


# ============================================================
# JSON-based context builders (compact, token-saving)
# ============================================================

def build_tour_context_json(db) -> Dict[str, Any]:
    tours = list_active_tours(db)
    return {
        "tour_dates": [
            {
                "index": i + 1,
                "date": t.date.strftime("%Y-%m-%d"),
                "display": t.date.strftime("%d/%m/%Y"),
                "id": t.id,
            }
            for i, t in enumerate(tours)
        ]
    }


def build_capacity_json(db) -> Dict[str, Any]:
    courses = list_courses(db)
    return {
        "capacity": {
            course.name: (
                course.capacity_available
                if course.capacity_available > 0
                else 0
            )
            for course in courses
        }
    }


def build_tour_suggestions(db) -> List[str]:
    tours = list_active_tours(db)
    return [
        f"{i+1}. {t.date.strftime('%d/%m/%Y')} · Cupo abierto"
        for i, t in enumerate(tours)
    ]


# ============================================================
# HTML Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/gracias", response_class=HTMLResponse)
def thank_you():
    return HTMLResponse(THANK_YOU_FILE.read_text(encoding="utf-8"))


# ============================================================
# New conversation initialization
# ============================================================

@app.get("/chat/init", response_model=InitChatResponse)
def init_chat(db=Depends(get_db_session)):
    conv_id = str(uuid4())

    conversations[conv_id] = ConversationThread()

    intro = (
        "Hola 👋 soy SAM, tu asistente de Admisiones del Montebello. "
        "¿En qué puedo ayudarte hoy? Estoy aquí para responder tus dudas "
        "y ayudarte a registrarte en el tour informativo cuando lo desees."
    )

    suggestions = build_tour_suggestions(db)
    conversations[conv_id].append("assistant", intro)

    return InitChatResponse(
        conversation_id=conv_id,
        reply=intro,
        stage="chat",
        suggested_tours=suggestions,
    )


# ============================================================
# Chat endpoint
# ============================================================

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db=Depends(get_db_session)):
    conv_id = req.conversation_id or str(uuid4())
    conversation = conversations.setdefault(conv_id, ConversationThread())

    # Append user message
    conversation.append("user", req.message)

    # Build compact JSON context
    tour_context = build_tour_context_json(db)
    capacity_context = build_capacity_json(db)

    # Call LLM
    raw = run_tourbot(
        conversation.history,
        conversation.summary,
        json.dumps(tour_context),
        json.dumps(capacity_context),
    )
    output = raw.output[0]

    suggestions = build_tour_suggestions(db)


    # ============================================================
    # FUNCTION CALL HANDLING
    # ============================================================
    if output.type == "function_call":
        fn_name = output.name

        # Safe JSON parsing
        try:
            args = json.loads(output.arguments)
        except Exception:
            reply = (
                "Creo que hubo un problema con los datos. "
                "¿Me confirmas nuevamente la fecha que deseas?"
            )
            conversation.append("assistant", reply)
            return ChatResponse(
                conversation_id=conv_id,
                reply=reply,
                stage="chat",
                registration_completed=False,
                wait_listed=False,
                suggested_tours=suggestions,
            )

        if fn_name == "register_user":

            # Validate required fields before executing
            if not isinstance(args.get("tour_date_id"), int):
                reply = "Necesito confirmar la fecha exacta del tour. ¿Cuál deseas?"
                conversation.append("assistant", reply)
                return ChatResponse(
                    conversation_id=conv_id,
                    reply=reply,
                    stage="chat",
                    registration_completed=False,
                    wait_listed=False,
                    suggested_tours=suggestions,
                )

            result = execute_register_user(db, args)

            if result.get("status") != "success":
                reply = (
                    "No logré completar el registro. "
                    "¿Podrías confirmarme nuevamente tus datos?"
                )
                conversation.append("assistant", reply)
                return ChatResponse(
                    conversation_id=conv_id,
                    reply=reply,
                    stage="chat",
                    registration_completed=False,
                    wait_listed=False,
                    suggested_tours=suggestions,
                )

            reply = (
                "¡Listo! 🙌 Tu registro al tour fue procesado con éxito. "
                "En breve recibirás la confirmación por correo."
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


    # ============================================================
    # NORMAL TEXT MESSAGE
    # ============================================================
    if output.type == "message":
        reply = output.content[0].text
        conversation.append("assistant", reply)

        return ChatResponse(
            conversation_id=conv_id,
            reply=reply,
            stage="chat",
            registration_completed=False,
            wait_listed=False,
            suggested_tours=suggestions,
        )
