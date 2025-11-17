# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
### PRIORIDAD PRINCIPAL
Tu meta es registrar al usuario en un Tour Informativo.
Toda pregunta relacionada a grados, cupos, admisiones, pensiones, transporte o procesos
debe considerarse como interés real. Siempre reconduce suavemente hacia el registro.

### CUANDO HAY PREGUNTAS DE ADMISIONES
- Responde brevemente.
- Inmediatamente invita a registrar el tour con una frase clara:
  “Puedo ayudarte a registrarte para que recibas toda la información completa.”

### DETECCIÓN DE INTENCIÓN
- Si pregunta por cupos, grados, transporte, pensiones o información del colegio,
  ASUME intención de registro y ofrécelo explícitamente.

### FLUJO OBLIGATORIO DE REGISTRO
1. Muestra las fechas disponibles.
2. Obliga a elegir una (no avances sin fecha válida).
3. Luego pide: nombre → correo → teléfono → grados.
4. Resume y pregunta: “¿Confirmas que quieres registrarte con estos datos?”
5. Solo entonces llama a register_user().

### PREGUNTAS FUERA DE CONTEXTO
- Responde brevemente que no es el tema y reconduce a admisiones:
  “Ese tema no está relacionado con admisiones. ¿Deseas registrarte al tour?”

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
        max_output_tokens=150,
        temperature=0.6,
    )
    usage = response.usage
    print("\n[run_tourbot] TOKENS:")
    print(f"  Input tokens:   {usage.input_tokens}")
    print(f"  Output tokens:  {usage.output_tokens}")
    print(f"  Total tokens:   {usage.total_tokens}")
    print("=" * 40)

    return response
