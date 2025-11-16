"""FastAPI entry point for the Montebello tour chatbot."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
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
    grade_status: str = "unknown"


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

GRADE_KEYWORDS: Dict[str, List[str]] = {
    "inicial": ["inicial", "prekinder", "pre-k", "preescolar"],
    "preparatoria": ["preparatoria", "kinder"],
    "primero": ["primero", "1ero", "1.\u00ba", "1ro"],
    "segundo": ["segundo", "2do", "2.\u00ba"],
    "tercero": ["tercero", "3ero", "3.\u00ba"],
    "cuarto": ["cuarto", "4to", "4.\u00ba"],
    "quinto": ["quinto", "5to", "5.\u00ba"],
    "sexto": ["sexto", "6to", "6.\u00ba"],
    "septimo": ["séptimo", "septimo", "7mo", "7.\u00ba"],
    "octavo": ["octavo", "8vo", "8.\u00ba"],
    "noveno": ["noveno", "9no", "9.\u00ba"],
    "decimo": ["décimo", "decimo", "10mo", "10.\u00ba"],
    "bachillerato": ["bachillerato", "11", "12", "13"],
}

GRADE_AVAILABILITY = {
    "inicial": "open",
    "preparatoria": "open",
    "primero": "open",
    "segundo": "waitlist",
    "tercero": "waitlist",
    "cuarto": "limited",
    "quinto": "limited",
    "sexto": "limited",
    "septimo": "limited",
    "octavo": "open",
    "noveno": "open",
    "decimo": "open",
    "bachillerato": "limited",
}

CONTEXT_KEYWORDS = [
    "tour",
    "cupo",
    "grado",
    "registro",
    "admis",
    "colegio",
    "montebello",
    "fecha",
    "transporte",
    "hanaska",
    "comida",
    "instalaciones",
]

OFFTOPIC_TRIGGERS = [
    "capital",
    "presidente",
    "mejor colegio",
    "clima",
    "fútbol",
    "matemáticas",
]

def friendly_name(conversation: ConversationState) -> str:
    name = conversation.data.get("name", "familia Montebello").strip()
    return name.split()[0].title() if name else "familia Montebello"


def stage_prompt(stage: str) -> str:
    prompts = {
        "name": "¿Con qué nombre te registro para coordinar el tour?",
        "email": "Necesito un correo para enviarte la confirmación.",
        "phone": "Compárteme un número para contactarte por llamada o WhatsApp.",
        "grade": GRADE_HINT,
        "date": "Elige la fecha que prefieras escribiendo el número o la fecha exacta de la lista.",
    }
    return prompts.get(stage, "¿Hay algo más que te gustaría saber del tour?")


def extract_grade_fragment(text: str) -> Optional[str]:
    lowered = text.lower()
    for _, keywords in GRADE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                return keyword
    match = re.search(r"(\d+)(?:\.?\s*(?:ero|do|to|mo))?\s*(?:de)?\s*(?:b[aá]sica|bachillerato)", lowered)
    if match:
        return match.group(0)
    return None


def describe_grade_availability(grade_text: str) -> Tuple[str, str, str, bool]:
    normalized = None
    lowered = grade_text.lower()
    for key, keywords in GRADE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            normalized = key
            break
    status = GRADE_AVAILABILITY.get(normalized or "general", "limited")
    display = grade_text.strip().title() if grade_text.strip() else (normalized or "Ese grado").title()
    if status == "open":
        message = f"Para {display} todavía contamos con cupos. Aprovechemos para asegurar tu visita."
    elif status == "limited":
        message = f"Para {display} nos quedan muy pocos espacios, por eso agendamos el tour cuanto antes."
    else:
        message = (
            f"{display} se maneja con lista prioritaria, pero al registrarte en el tour te reservamos ese lugar para avisarte en cuanto se libere."
        )
    return normalized or "general", status, message, status == "waitlist"


def is_off_topic_message(message: str) -> bool:
    text = message.lower()
    if any(keyword in text for keyword in CONTEXT_KEYWORDS):
        return False
    if any(trigger in text for trigger in OFFTOPIC_TRIGGERS):
        return True
    return "?" in text


def redirect_off_topic(conversation: ConversationState) -> str:
    name = friendly_name(conversation)
    if conversation.stage == "completed":
        return (
            f"Lo siento {name}, esa conversación se sale de lo que puedo resolver aquí. "
            "Tu registro ya está confirmado y podemos continuar en el tour para conversar de otros temas."
        )
    return (
        f"Lo siento {name}, necesito mantener el enfoque en tu registro al Tour de Admisiones. "
        + stage_prompt(conversation.stage)
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
        "Después podrás elegir una fecha escribiendo el número exacto de la lista. "
        "Para empezar, ¿con qué nombre te gustaría que te contacte el equipo?"
    )
    return polish_reply(draft), suggestions


def format_tour_option(index: int, tour: TourDate) -> str:
    status = "Cupo inmediato"
    return f"{index}. {tour.date.strftime('%d/%m/%Y')} · {status} · grupos de {tour.capacity} familias"


def process_message(
    conversation: ConversationState, message: str, db: sqlite3.Connection
) -> tuple[str, str, bool, List[str]]:
    normalized = message.strip()
    conversation.history.append({"role": "user", "content": normalized})

    info_block = detect_information_request(normalized, db)
    if not info_block and is_off_topic_message(normalized):
        redirect = redirect_off_topic(conversation)
        polished = polish_reply(redirect)
        conversation.history.append({"role": "assistant", "content": polished})
        return polished, conversation.stage, conversation.wait_listed, []
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
            wait_listed = conversation.wait_listed
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
            f"{tour.date.strftime('%d/%m')} (cupo inmediato)" for tour in tours
        ]
        return (
            "Cada fecha publicada tiene cupo confirmado. Próximas fechas: "
            + ", ".join(counts)
            + ". Solo elige el número de la fecha que prefieras y seguimos con tu registro."
        )

    grade_fragment = extract_grade_fragment(text)
    if grade_fragment:
        _, _, grade_message, _ = describe_grade_availability(grade_fragment)
        return grade_message + " Si quieres, puedo reservar tu visita al tour informativo."

    for keyword, text_block in INFO_BLOCKS.items():
        if keyword in text:
            return text_block

    if "grado" in text or "curso" in text:
        return GRADE_HINT

    if "mejor" in text and "colegio" in text:
        return (
            "Existen muchas instituciones que buscan lo mismo que Montebello, "
            "pero nuestra misión es formar niños cristocéntricos y preparados para triunfar dentro y fuera del país. "
            "Por eso vale la pena visitarnos en el tour y conocer los testimonios de nuestras familias."
        )

    return None


def handle_name(conversation: ConversationState, message: str) -> tuple[bool, str]:
    lowered = message.lower()
    if "?" in message or any(keyword in lowered for keyword in CONTEXT_KEYWORDS):
        return False, "Te responderé con todo detalle apenas registre tu nombre. ¿Cómo te llamas?"
    if len(message) < 2:
        return False, "¿Podrías indicarme tu nombre completo para personalizar la reserva?"
    clean_name = re.sub(
        r"^(hola|buen[oa]s)?\s*(me llamo|soy)\s+",
        "",
        message.strip(),
        flags=re.IGNORECASE,
    ).strip()
    if not clean_name:
        clean_name = message.strip()
    conversation.data["name"] = clean_name
    return (
        True,
        f"Gracias, {clean_name.strip().title()} 🙌. ¿Cuál es el correo electrónico de contacto para enviarte la confirmación?",
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
    normalized, status, grade_msg, wait_flag = describe_grade_availability(message)
    conversation.data["grade_key"] = normalized
    conversation.grade_status = status
    conversation.wait_listed = wait_flag
    return (
        True,
        grade_msg
        + " Todas las fechas que verás tienen cupos confirmados; indícame el número exacto o haz clic en la opción para agendarte.",
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
            f"No encontré esa fecha. Escribe el número exacto o copia la fecha tal como aparece:\n{options}",
            conversation.wait_listed,
            suggestions,
        )

    force_wait_listed = conversation.grade_status == "waitlist" or conversation.wait_listed
    _, wait_listed = create_registration(
        db,
        first_name=conversation.data.get("name", ""),
        last_name="",
        email=conversation.data.get("email", ""),
        phone=conversation.data.get("phone", ""),
        grade_interest=conversation.data.get("grade", ""),
        tour_date=tour,
        force_wait_listed=force_wait_listed,
    )

    grade_name = conversation.data.get("grade", "tu grado de interés").strip() or "tu grado de interés"
    status_msg = (
        f"Te registré para {grade_name} en lista prioritaria; en cuanto se abra un espacio te avisaremos."
        if wait_listed
        else f"¡Tu cupo para {grade_name} quedó reservado!"
    )
    follow_up = (
        "El equipo de Admisiones te escribirá con la confirmación, recomendaciones y detalles logísticos."
    )
    return (
        True,
        f"Listo, te agendé para el tour del {tour.date.strftime('%d/%m/%Y')}. {status_msg} {follow_up}"
        " ¡Nos vemos muy pronto en el campus! ¿Hay algo más que te gustaría saber sobre Montebello?",
        wait_listed,
        suggestions,
    )


def handle_follow_up(
    conversation: ConversationState, message: str, db: sqlite3.Connection
) -> tuple[str, bool, List[str]]:
    info = detect_information_request(message, db)
    name = friendly_name(conversation)
    if info:
        reply = info + "\nSi deseas registrar a otro integrante solo indícame su nombre y grado."
    else:
        reply = (
            f"Gracias por tu confianza, {name}. Tu registro quedó listo y este chat sigue abierto por si"
            " quieres otra fecha o más información."
        )
    return reply, conversation.wait_listed, []
