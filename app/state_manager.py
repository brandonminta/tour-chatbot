# app/state_manager.py


from __future__ import annotations
from typing import List, Dict, Any
from .openai_client import _client

EXTRACTION_PROMPT = """
Extrae del diálogo solo los datos mencionados.
No inventes nada.

Debes devolver este JSON:

{
  "name": "",
  "email": "",
  "phone": "",
  "grades": [],
  "intent": "unknown | info | question | register",
  "ready_for_registration": false
}

Reglas:
- intent="register" si el usuario quiere separar cupo, asistir o agendar.
- ready_for_registration=true solo si name, email, phone y grades[] están completos.
- Si algún dato no aparece, déjalo vacío.
"""

def extract_state(history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Performs semantic extraction using a small JSON-only model.
    Only the last few user/assistant turns are sent to reduce token usage.
    """

    # No client (offline mode)
    if not _client:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "grades": [],
            "intent": "unknown",
            "ready_for_registration": False,
        }

    # Keep only last 4 messages
    slim_history = history[-4:]

    # Convert to minimal text for lower token usage
    dialogue_text = "\n".join(
        f"{m['role'][0].upper()}: {m['content']}" for m in slim_history
    )

    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": dialogue_text},
    ]

    try:
        completion = _client.responses.create(
            model="gpt-4o-mini",
            input=messages,                          
            response_format={"type": "json_object"},  
            temperature=0,
            max_output_tokens=120,
        )

        return completion.output[0].content[0].json

    except Exception as e:
        print("State extraction failed:", e)
        return {
            "name": "",
            "email": "",
            "phone": "",
            "grades": [],
            "intent": "unknown",
            "ready_for_registration": False,
        }
