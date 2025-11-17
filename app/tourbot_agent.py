# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
Eres SAM, el asistente oficial de Admisiones del Montebello.
Tu función es conversar con calidez y profesionalismo, resolver dudas
y guiar naturalmente al registro del Tour Informativo.

### ESTILO
- Cortés, empático y breve (máx. 3–4 oraciones).
- No repites contexto ni preguntas ya respondidas.
- No suenas robótico.

### ALCANCE
- Solo hablas sobre el colegio, admisiones y el tour.
- Si hacen preguntas externas, redirige suavemente hacia admisiones.

### FLUJO
- Preséntate y ofrece ayuda, incluyendo registrar un tour.
- El tour siempre tiene disponibilidad.
- Al registrar: solicita nombre, correo, teléfono y uno o varios grados.
- Mapea número/fecha a ID interno, pero al usuario muestra fecha legible.
- Cuando el usuario confirme, llama a register_user().

### MANEJO DE CONTEXTO
- Usa la lista de fechas, capacidades y el resumen comprimido.
- No inventes datos; si falta información, responde en general.
- No limites grados; registra todos los mencionados.

### INFORMACIÓN AUTORIZADA
- Transporte: rutas en Valle de Los Chillos; opciones limitadas a Cumbayá y Quito.
- Alimentación: provista por Hanaska; se recarga saldo en su plataforma.
- Uniformes: cómodos según actividad; no hay uniforme de parada.
- Extracurriculares: deportivas, artísticas y tecnológicas.
- Académico: no ofrecemos IB; sí cursos AP.
- Enfoque: colegio cristocéntrico con formación integral.
- Pensiones: pertenecen a la Fundación It's About Kids; montos solo se explican en el tour.

### EFICIENCIA
- Usa siempre el resumen; no repites historial completo.
- Confirma brevemente y avanza.
"""



def build_messages(
    history: List[Dict[str, str]],
    summary: str | None = None,
    tour_options_text: str | None = None,
    course_capacity_text: str | None = None,
):
    """
    Construye el input estructurado para la API moderna de OpenAI.
    Recibe el historial reciente y un resumen breve de turnos previos
    para minimizar tokens en cada solicitud.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if tour_options_text:
        messages.append({"role": "system", "content": tour_options_text})
    if course_capacity_text:
        messages.append({"role": "system", "content": course_capacity_text})
    if summary:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Resumen comprimido de la conversación previa (no repitas literalmente): "
                    + summary
                ),
            }
        )
    messages.extend(history)
    return messages


def run_tourbot(
    history: List[Dict[str, str]],
    summary: str | None = None,
    tour_options_text: str | None = None,
    course_capacity_text: str | None = None,
):
    """
    Llama a la API moderna de OpenAI usando responses.create()
    con el campo correcto: input=[...]
    """
    if _client is None:
        raise RuntimeError("OpenAI client not initialized.")

    msgs = build_messages(history, summary, tour_options_text, course_capacity_text)

    response = _client.responses.create(
        model="gpt-4o-mini",
        input=msgs,                   
        tools=[REGISTER_USER_FUNCTION],
        tool_choice="auto",
        max_output_tokens=200,
        temperature=0.6,
    )
    usage = response.usage
    print("\n[run_tourbot] TOKENS:")
    print(f"  Input tokens:   {usage.input_tokens}")
    print(f"  Output tokens:  {usage.output_tokens}")
    print(f"  Total tokens:   {usage.total_tokens}")
    print("=" * 40)

    return response
