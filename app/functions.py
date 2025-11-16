# app/functions.py
"""
Defines function-calling schemas and real backend executors for the TourBot.
"""

from __future__ import annotations
from typing import Dict, Any
from .database import create_registration, list_active_tours, find_tour_by_input


# OpenAI function schema
REGISTER_USER_FUNCTION = {
    "name": "register_user",
    "description": "Registra a una familia en un Tour Informativo del Colegio Montebello.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "grade": {"type": "string"},
            "tour_date_id": {"type": "integer"},
        },
        "required": ["name", "email", "phone", "grade", "tour_date_id"],
    },
}


def execute_register_user(db, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the actual DB registration using create_registration().
    Args must include:
    name, email, phone, grade, tour_date_id
    """

    # split name into first + last
    name = args["name"].strip()
    parts = name.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    # fetch tour date object
    tours = list_active_tours(db)
    tour = next((t for t in tours if t.id == args["tour_date_id"]), None)
    if not tour:
        return {"status": "error", "message": "tour_date_id inválido"}

    # create DB registration
    reg, wait_listed = create_registration(
        db,
        first_name=first_name,
        last_name=last_name,
        email=args["email"],
        phone=args["phone"],
        grade_interest=args["grade"],
        tour_date=tour,
        force_wait_listed=False,  # model can adjust later if needed
    )

    return {
        "status": "success",
        "registration_id": reg.id,
        "wait_listed": wait_listed,
        "tour_date": str(tour.date),
    }
