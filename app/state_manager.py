# app/state_manager.py
"""
Semantic extractor for user profile data in the Montebello TourBot.
Uses a lightweight OpenAI JSON-extraction model.
"""

from __future__ import annotations
from typing import List, Dict, Any
from .openai_client import _client

EXTRACTION_PROMPT = """
Eres un analizador que toma el historial completo de un chat entre un usuario 
y SAM (asistente de Admisiones Montebello), y devuelve un JSON estructurado.

Reglas:
- No inventes datos.
- Solo usa la información que realmente aparece en el diálogo.
- Si un dato no aparece, déjalo como cadena vacía "".
- Debes inferir si el usuario tiene intención de registrarse.
- Esta extracción NO es la respuesta del chatbot; es solo análisis.

Campos que debes devolver:

{
  "name": "",
  "email": "",
  "phone": "",
  "grade": "",
  "intent": "unknown | question | info | register",
  "ready_for_registration": false
}

Criterios:

intent:
- "register": si el usuario expresa deseo de asistir, separar cupo, agendar, registrarse.
- "question": si hace preguntas sobre cupos, grados, proceso.
- "info": si solo busca información general.
- "unknown": si no se puede determinar.

ready_for_registration:
- true si name, email, phone y grade están presentes y válidos.
- false si falta cualquiera de ellos.
"""

def extract_state(history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Ejecuta una extracción semántica del estado actual del usuario
    basado en el historial de conversación.
    """

    if not _client:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "grade": "",
            "intent": "unknown",
            "ready_for_registration": False
        }

    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": str(history)}
    ]

    try:
        completion = _client.responses.create(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_output_tokens=200,
        )

        return completion.output[0].content[0].json  # extracción JSON directa

    except Exception:
        # fallback vacio
        return {
            "name": "",
            "email": "",
            "phone": "",
            "grade": "",
            "intent": "unknown",
            "ready_for_registration": False
        }
