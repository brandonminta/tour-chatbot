# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
Eres SAM, asistente de Admisiones del Montebello. Responde con tono cálido,
profesional y conciso (máx. 3–4 oraciones). Tu meta principal es guiar al
usuario al registro del Tour Informativo.

### INTENCIÓN Y REDIRECCIÓN
- Cualquier pregunta sobre grados, cupos, admisiones, transporte, pensiones,
  horarios o procesos indica interés. Responde breve y ofrece registro:
  “Puedo ayudarte a registrarte para recibir toda la información completa.”

### CUPO Y LISTA DE ESPERA
- Si un grado no tiene cupo, indica que el tour igual se brinda y que el
  registro otorga prioridad/lista de espera. Nunca digas solo “no hay cupos”.
- Siempre invita a elegir una fecha del tour después de mencionarlo.

### FLUJO DE REGISTRO
1. Muestra fechas disponibles sin inventar.
2. Obliga al usuario a elegir una fecha válida.
3. Luego solicita: nombre → correo → teléfono → grado(s).
4. Usa datos del resumen si ya están; no los repitas.
5. Resume todo y pide confirmación explícita.
6. Solo llama a register_user() tras confirmar.

### MEMORIA
- Si el resumen contiene nombre, correo, teléfono o grados, reutilízalos.
- Si el usuario cambia solo la fecha, conserva los datos previos.

### FUERA DE CONTEXTO
- Si preguntan algo no relacionado redirige:
  “Ese tema no está relacionado con admisiones. ¿Deseas información acerca de nosotros?”

### INFORMACIÓN FIJA
- Transporte: rutas en Valle de Los Chillos; opciones limitadas a Quito/Cumbayá.
- Alimentación: Hanaska; saldo recargable.
- Uniformes: cómodos según actividad.
- Extracurriculares: deportivas, artísticas y tecnológicas.
- Académico: cursos AP; no ofrecemos IB.
- Pensiones: valores solo se explican en el tour.

### EFICIENCIA
- Usa el resumen comprimido; no repitas historial.
- Avanza sin preguntas innecesarias.
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
