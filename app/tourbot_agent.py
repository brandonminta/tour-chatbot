# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
Eres SAM, asistente de Admisiones del Colegio Montebello.

Puedes conversar naturalmente y también llamar funciones cuando
sea necesario registrar a un usuario.

Reglas:
- Cuando tengas: nombre, email, teléfono, grado y tour_date_id,
  y el usuario confirme que quiere registrarse,
  debes llamar automáticamente a la función register_user().
- No inventes datos.
- Si falta información, pídele al usuario suavemente que la confirme.
"""

def build_messages(history: List[Dict[str, str]]):
    return [{"role": "system", "content": SYSTEM_PROMPT}] + history


def run_tourbot(history: List[Dict[str, str]]):
    msgs = build_messages(history)

    response = _client.responses.create(
        model="gpt-4.1-mini",
        messages=msgs,
        tools=[{"type": "function", "function": REGISTER_USER_FUNCTION}],
        tool_choice="auto",
        temperature=0.6,
        max_output_tokens=350,
    )

    return response
