"""FastAPI entry point for the Montebello tour chatbot."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .database import (
    TourDate,
    create_registration,
    find_tour_by_input,
    get_db_session,
    init_db,
    list_active_tours,
)
from .openai_client import polish_reply
from .schemas import ChatRequest, ChatResponse, InitChatResponse


@dataclass
class ConversationState:
    id: str
    stage: str = "welcome"
    data: Dict[str, str] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    wait_listed: bool = False


conversation_store: Dict[str, ConversationState] = {}


INFO_BLOCKS = {
    "cupos": (
        "Actualmente manejamos grupos pequeños para garantizar una experiencia personalizada.\n"
        "Siempre confirmaremos tu cupo apenas registres la fecha que prefieras"
    ),
    "instalaciones": (
        "Durante el tour podrás recorrer aulas, laboratorios, canchas, huertos y espacios creativos."
    ),
    "transporte": (
        "Contamos con rutas de transporte escolar en los principales sectores de Quito y los valles."
    ),
    "comida": (
        "El servicio Hanaska ofrece alimentación saludable preparada en el campus para estudiantes y visitantes."
    ),
    "hanaska": (
        "Hanaska prepara menús balanceados y con opciones especiales durante cada jornada de visitas."
    ),
    "proceso": (
        "El tour incluye una inducción del equipo de Admisiones y acompañamiento para el proceso de aplicación."
    ),
}

GRADE_HINT = (
    "Atendemos desde Inicial 2 hasta 3.º de Bachillerato. Indícame el grado o rango que te interesa."
)


app = FastAPI(title="SAM - Montebello Tour Chatbot", version="1.0.0")
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
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/chat/init", response_model=InitChatResponse)
def init_chat(db: sqlite3.Connection = Depends(get_db_session)) -> InitChatResponse:
    conversation = create_conversation()
    reply, suggestions = build_welcome_message(db)
    return InitChatResponse(
        conversation_id=conversation.id, reply=reply, stage="name", suggested_tours=suggestions
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: sqlite3.Connection = Depends(get_db_session)) -> ChatResponse:
    if not req.message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    conversation = get_or_create_conversation(req.conversation_id)
    reply, next_stage, wait_listed, suggestions = process_message(
        conversation, req.message, db
    )

    conversation.stage = next_stage
    conversation.wait_listed = wait_listed
    return ChatResponse(
        reply=reply,
        conversation_id=conversation.id,
        stage=next_stage,
        registration_completed=next_stage == "completed",
        wait_listed=wait_listed,
        suggested_tours=suggestions,
    )


def create_conversation() -> ConversationState:
    conversation_id = str(uuid4())
    state = ConversationState(id=conversation_id, stage="name")
    conversation_store[conversation_id] = state
    return state


def get_or_create_conversation(conversation_id: Optional[str]) -> ConversationState:
    if conversation_id and conversation_id in conversation_store:
        return conversation_store[conversation_id]
    return create_conversation()


def build_welcome_message(db: sqlite3.Connection) -> tuple[str, List[str]]:
    tours = list_active_tours(db)
    suggestions = [format_tour_option(idx, tour) for idx, tour in enumerate(tours, start=1)]
    draft = (
        "Hola, soy SAM 🤖 del Colegio Montebello. Estoy aquí para ayudarte a separar un cupo en el Tour de Admisiones.\n"
        "Te contaré sobre cupos, grados, transporte, alimentación Hanaska y todo el proceso. "
        "Para empezar, ¿con qué nombre te gustaría que te contacte el equipo?"
    )
    return polish_reply(draft), suggestions


def format_tour_option(index: int, tour: TourDate) -> str:
    status = (
        "Cupos disponibles" if tour.available_slots > 0 else "Lista prioritaria"
    )
    return f"{index}. {tour.date.strftime('%d/%m/%Y')} · {status} (capacidad {tour.capacity})"


def process_message(
    conversation: ConversationState, message: str, db: sqlite3.Connection
) -> tuple[str, str, bool, List[str]]:
    normalized = message.strip()
    conversation.history.append({"role": "user", "content": normalized})

    info_block = detect_information_request(normalized, db)
    base_reply = ""
    next_stage = conversation.stage
    wait_listed = conversation.wait_listed
    suggestions = []

    if conversation.stage == "name":
        success, base_reply = handle_name(conversation, normalized)
        next_stage = "email" if success else "name"
    elif conversation.stage == "email":
        success, base_reply = handle_email(conversation, normalized)
        next_stage = "phone" if success else "email"
    elif conversation.stage == "phone":
        success, base_reply = handle_phone(conversation, normalized)
        next_stage = "grade" if success else "phone"
    elif conversation.stage == "grade":
        success, base_reply = handle_grade(conversation, normalized)
        next_stage = "date" if success else "grade"
        if success:
            suggestions = [
                format_tour_option(idx, tour)
                for idx, tour in enumerate(list_active_tours(db), start=1)
            ]
    elif conversation.stage == "date":
        success, base_reply, wait_listed, suggestions = handle_date(conversation, normalized, db)
        next_stage = "completed" if success else "date"
    else:
        base_reply, wait_listed, suggestions = handle_follow_up(conversation, normalized, db)
        next_stage = "completed"

    if info_block:
        base_reply = f"{info_block}\n\n{base_reply}"

    polished = polish_reply(base_reply)
    conversation.history.append({"role": "assistant", "content": polished})
    return polished, next_stage, wait_listed, suggestions


def detect_information_request(message: str, db: sqlite3.Connection) -> Optional[str]:
    text = message.lower()
    tours = list_active_tours(db)
    if any(keyword in text for keyword in ["cupo", "disponibilidad", "lleno", "prioridad"]):
        counts = [
            f"{tour.date.strftime('%d/%m')} ({tour.available_slots} cupos)"
            if tour.available_slots > 0
            else f"{tour.date.strftime('%d/%m')} (lista prioritaria)"
            for tour in tours
        ]
        return (
            "Tenemos grupos reducidos por jornada. Próximas fechas: "
            + ", ".join(counts)
            + ". Registra tu cupo y, si alguna fecha está llena, te ubicamos en la lista prioritaria."
        )

    for keyword, text_block in INFO_BLOCKS.items():
        if keyword in text:
            return text_block

    if "grado" in text or "curso" in text:
        return GRADE_HINT

    return None


def handle_name(conversation: ConversationState, message: str) -> tuple[bool, str]:
    if len(message) < 2:
        return False, "¿Podrías indicarme tu nombre completo para personalizar la reserva?"
    conversation.data["name"] = message.strip()
    return (
        True,
        f"Gracias, {message.strip().title()} 🙌. ¿Cuál es el correo electrónico de contacto para enviarte la confirmación?",
    )


def handle_email(conversation: ConversationState, message: str) -> tuple[bool, str]:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message):
        return False, "Creo que el formato del correo no es válido. ¿Puedes revisarlo y volver a enviarlo?"
    conversation.data["email"] = message.strip()
    return True, "Perfecto. ¿A qué número celular puedo llamarte o escribirte por WhatsApp?"


def handle_phone(conversation: ConversationState, message: str) -> tuple[bool, str]:
    digits = re.sub(r"[^0-9]", "", message)
    if len(digits) < 7:
        return False, "Necesito un número telefónico válido (incluye código de país si estás fuera de Ecuador)."
    conversation.data["phone"] = message.strip()
    return (
        True,
        "Gracias. ¿Para qué grado o curso estás interesado? Atendemos desde Inicial 2 hasta 3.º de Bachillerato.",
    )


def handle_grade(conversation: ConversationState, message: str) -> tuple[bool, str]:
    if len(message) < 2:
        return False, GRADE_HINT
    conversation.data["grade"] = message.strip()
    return (
        True,
        "Excelente. Estas son las próximas fechas disponibles. Indícame el número o la fecha que prefieras para agendar el tour.",
    )


def handle_date(
    conversation: ConversationState, message: str, db: sqlite3.Connection
) -> tuple[bool, str, bool, List[str]]:
    tours = list_active_tours(db)
    suggestions = [format_tour_option(idx, tour) for idx, tour in enumerate(tours, start=1)]
    tour = find_tour_by_input(db, message)
    if not tour:
        options = "\n".join(suggestions)
        return (
            False,
            f"No encontré esa fecha. Elige una de estas opciones:\n{options}",
            conversation.wait_listed,
            suggestions,
        )

    _, wait_listed = create_registration(
        db,
        first_name=conversation.data.get("name", ""),
        last_name="",
        email=conversation.data.get("email", ""),
        phone=conversation.data.get("phone", ""),
        grade_interest=conversation.data.get("grade", ""),
        tour_date=tour,
    )

    status_msg = (
        "Te registré en lista prioritaria; en cuanto se abra un espacio te avisaremos."
        if wait_listed
        else "¡Tu cupo quedó reservado!"
    )
    follow_up = (
        "El equipo de Admisiones te escribirá con la confirmación y recomendaciones para tu visita."
    )
    return (
        True,
        f"Listo, registré tu interés para el tour del {tour.date.strftime('%d/%m/%Y')}. {status_msg} {follow_up}"
        " ¿Hay algo más que te gustaría saber sobre Montebello?",
        wait_listed,
        suggestions,
    )


def handle_follow_up(
    conversation: ConversationState, message: str, db: sqlite3.Connection
) -> tuple[str, bool, List[str]]:
    info = detect_information_request(message, db)
    if info:
        reply = info + "\n¿Te gustaría que reservemos otro familiar o fecha adicional?"
    else:
        reply = (
            "Gracias por escribirnos. Tu registro está listo y puedes responder este chat si necesitas otro acompañamiento."
        )
    return reply, conversation.wait_listed, []
