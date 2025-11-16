"""Optional helper to rewrite responses with OpenAI."""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

try:  # Optional import to avoid breaking when key is missing
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback when SDK unavailable
    OpenAI = None  # type: ignore

load_dotenv()

_API_KEY = os.getenv("OPENAI_API_KEY")
_client: Optional[OpenAI] = None
if _API_KEY and OpenAI is not None:
    try:
        _client = OpenAI(api_key=_API_KEY)
    except Exception:
        _client = None

SYSTEM_PROMPT = """
Eres SAM, el asistente virtual de Admisiones del Montebello.
Tu tarea es tomar mensajes base (en español) y devolverlos en un tono cálido,
profesional e invitando a las familias a registrarse en el Tour de Admisiones.
No inventes datos nuevos; solo mejora la redacción dada.
"""


def polish_reply(draft: str) -> str:
    """Return an enhanced reply using OpenAI when available."""
    if not draft.strip():
        return draft

    try:
        completion = _client.responses.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Reescribe el siguiente mensaje manteniendo la intención original:\n" + draft,
                },
            ],
            temperature=0.6,
            max_output_tokens=350,
        )
        return completion.output_text or draft
    except Exception:
        return draft
