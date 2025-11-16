# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
Eres SAM, asistente de Admisiones del Colegio Montebello.

Conversas amablemente, extraes datos naturalmente
y cuando tengas nombre, email, teléfono, grado y tour_date_id
y el usuario confirme que quiere registrarse,
debes llamar a la función register_user().

No inventes datos. Pide aclaraciones con suavidad.
"""


def build_messages(history: List[Dict[str, str]]):
    """
    Construye el input estructurado para la API moderna de OpenAI.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    return messages


def run_tourbot(history: List[Dict[str, str]]):
    """
    Llama a la API moderna de OpenAI usando responses.create()
    con el campo correcto: input=[...]
    """
    if _client is None:
        raise RuntimeError("OpenAI client not initialized.")

    msgs = build_messages(history)

    response = _client.responses.create(
        model="gpt-4o-mini",
        input=msgs,                   
        tools=[REGISTER_USER_FUNCTION],
        tool_choice="auto",
        max_output_tokens=350,
        temperature=0.6,
    )

    return response
