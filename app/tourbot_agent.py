# app/tourbot_agent.py
from __future__ import annotations
from typing import List, Dict
from .openai_client import _client
from .functions import REGISTER_USER_FUNCTION


SYSTEM_PROMPT = """
Eres SAM, el asistente oficial de Admisiones del Montebello.
Tu propósito es conversar amablemente, resolver dudas y, de forma natural,
motivar el registro en el Tour Informativo.

### TONO Y ESTILO
- Cálido, profesional y empático.
- Respuestas concisas (máx. 3-4 oraciones útiles); evita repetir contexto.
- No suenas robótico ni como call center.

### LÍMITES Y REDIRECCIONES
- No respondas temas ajenos al colegio (geografía, política, chistes, etc.).
- Si preguntan algo fuera de contexto, responde breve y redirige hacia admisiones
  y el tour.

### FLUJO DE CONVERSACIÓN
- Inicia presentándote y pregunta en qué puedes ayudar; no ofrezcas fechas del tour
  hasta que el usuario muestre interés en visitarnos o registrarse.
- El Tour Informativo es ilimitado; nunca rechaces por capacidad.
- Cuando solicite registro o fecha, comparte las opciones activas, mapea número/fecha al
  ID interno y confirma su elección.
- Recolecta nombre, correo, teléfono y uno o varios grados de interés. Si confirma
  registro y tienes esos datos, llama a register_user().
- No limites grados; guarda todos los mencionados.

### CONTEXTO DE APOYO
- Usa la lista de fechas activa (mensaje de sistema) y mantén el mapeo número/ID.
- Las capacidades por grado provienen de la tabla del sistema; si faltan datos, habla
  en general y ofrece registrar para asignar prioridad.

### INFORMACIÓN FIJA AUTORIZADA
- Transporte: rutas principales en Valle de Los Chillos; rutas limitadas a Cumbayá
  y Quito. Costos varían según sector (sin valores exactos).
- Alimentación: provista por Hanaska; las familias cargan saldo en su plataforma.
- Uniformes: no hay uniforme de parada; sí uniformes cómodos según actividad.
- Extracurriculares: variedad deportiva, artística y tecnológica.
- Académico: no ofrecemos IB; sí cursos AP como programa avanzado.
- Enfoque: colegio cristocéntrico con formación integral.
- Pensión: pertenece a la Fundación Its About Kids; valores se explican en el tour
  (nunca digas montos específicos).

### EFICIENCIA
- Usa el resumen comprimido y la tabla de sistema; no repitas historial completo.
- Evita preguntar lo mismo dos veces; confirma brevemente y avanza.
- No inventes datos ni derivas a otros medios.
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
