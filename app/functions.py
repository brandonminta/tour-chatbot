# app/functions.py

from __future__ import annotations
from typing import Dict, Any
from .database import create_registration, list_active_tours

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
            "grade": {"type": "string"},
            "tour_date_id": {"type": "integer"},
        },
        "required": ["name", "email", "phone", "grade", "tour_date_id"]
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

    # ejecutar registro real
    reg, wait_listed = create_registration(
        db,
        first_name=first_name,
        last_name=last_name,
        email=args["email"],
        phone=args["phone"],
        grade_interest=args["grade"],
        tour_date=tour,
        force_wait_listed=False,
    )

    return {
        "status": "success",
        "registration_id": reg.id,
        "wait_listed": wait_listed,
        "tour_date": str(tour.date),
    }
