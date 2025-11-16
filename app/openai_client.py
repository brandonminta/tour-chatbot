# app/openai_client.py

"""
OpenAI client singleton for all chatbot components.
Provides:
- _client  → shared OpenAI client
- polish_reply() → optional text rewriting
"""

from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ------------------------------------------
# Create a global OpenAI client
# ------------------------------------------

_API_KEY = os.getenv("OPENAI_API_KEY")
_client: OpenAI = OpenAI(api_key=_API_KEY) if _API_KEY else None

# ------------------------------------------
# Polisher prompt
# ------------------------------------------

SYSTEM_PROMPT = """
Eres SAM, el asistente virtual de Admisiones del Montebello.
Tu tarea es tomar mensajes base (en español) y devolverlos en un tono cálido,
profesional e invitando a las familias a registrarse en el Tour de Admisiones.
No inventes datos nuevos; solo mejora la redacción dada.
"""

# ------------------------------------------
# Rewrite helper
# ------------------------------------------

def polish_reply(draft: str) -> str:
    """Rewrite a message in SAM’s tone."""
    if not draft.strip() or not _client:
        return draft

    try:
        completion = _client.responses.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Reescribe el siguiente mensaje manteniendo la intención original:\n" + draft
                    ),
                },
            ],
            temperature=0.6,
            max_output_tokens=350,
        )
        return completion.output_text or draft

    except Exception:
        return draft
