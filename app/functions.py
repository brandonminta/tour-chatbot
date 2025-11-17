# app/functions.py

from __future__ import annotations
from typing import Dict, Any
from .database import create_registration, list_active_tours, reserve_course_interest

# ---------- CORRECT FORMAT FOR NEW OPENAI API ---------- #
REGISTER_USER_FUNCTION = {
    "type": "function",
    "name": "register_user",
    "description": "Registra a una familia para un tour informativo del Colegio Montebello.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "grades": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de grados de interés (acepta múltiples).",
                "minItems": 1,
            },
            "tour_date_id": {"type": "integer"},
        },
        "required": ["name", "email", "phone", "grades", "tour_date_id"]
    }
}
# -------------------------------------------------------- #


def execute_register_user(db, args: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta el registro real en SQLite usando create_registration()."""

    # separar nombre
    name = args["name"].strip()
    parts = name.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    # buscar tour por ID
    tours = list_active_tours(db)
    tour = next((t for t in tours if t.id == args["tour_date_id"]), None)
    if not tour:
        return {"status": "error", "message": "tour_date_id inválido"}

    grades_raw = args.get("grades") or args.get("grade") or ""
    if isinstance(grades_raw, list):
        grades_list = [g.strip() for g in grades_raw if isinstance(g, str) and g.strip()]
    elif isinstance(grades_raw, str):
        grades_list = [g.strip() for g in grades_raw.split(",") if g.strip()]
    else:
        grades_list = []

    grade_interest = ", ".join(grades_list) or "sin especificar"

    # Marcar disponibilidad por grado y usarlo para reflejar lista de espera
    course_status = reserve_course_interest(db, grades_list)

    # ejecutar registro real
    reg, wait_listed = create_registration(
        db,
        first_name=first_name,
        last_name=last_name,
        email=args["email"],
        phone=args["phone"],
        grade_interest=grade_interest,
        tour_date=tour,
        force_wait_listed=course_status.get("wait_listed", False),
    )

    return {
        "status": "success",
        "registration_id": reg.id,
        "wait_listed": wait_listed,
        "tour_date": str(tour.date),
        "course_status": course_status,
    }
