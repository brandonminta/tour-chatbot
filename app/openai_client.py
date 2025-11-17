# app/openai_client.py


from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------
# GLOBAL CLIENT
# ---------------------------------------------------
_API_KEY = os.getenv("OPENAI_API_KEY")
_client: OpenAI = OpenAI(api_key=_API_KEY) if _API_KEY else None

# ---------------------------------------------------
# POLISHER (minimal prompt to reduce token usage)
# ---------------------------------------------------
POLISH_PROMPT = "Reescribe el texto con tono cálido y profesional, sin agregar información nueva."

DEBUG_POLISH = True   


def polish_reply(draft: str) -> str:
    """Rewrite a message in a warm, concise tone."""
    if not draft.strip() or not _client:
        return draft

    try:
        completion = _client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": POLISH_PROMPT},
                {"role": "user", "content": draft}
            ],
            temperature=0.4,
            max_output_tokens=80
        )

        if DEBUG_POLISH:
            usage = completion.usage
            print("\n[polish_reply] TOKENS:")
            print(f"  Input tokens p:   {usage.input_tokens}")
            print(f"  Output tokens p:  {usage.output_tokens}")
            print(f"  Total tokens p:   {usage.total_tokens}")
            print("-" * 40)

        return completion.output_text or draft

    except Exception:
        return draft
