# app/functions.py

from __future__ import annotations
from typing import Dict, Any
from .database import create_registration, list_active_tours, reserve_course_interest

# -------------------------------------------------------------------------- #
#  FUNCTION SCHEMA optimized for minimal tokens and consistent usage
# -------------------------------------------------------------------------- #

REGISTER_USER_FUNCTION = {
    "type": "function",
    "name": "register_user",
    "description": "Registra a una familia en un tour informativo.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "grades": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1
            },
            "tour_date_id": {"type": "integer"}
        },
        "required": ["name", "email", "phone", "grades", "tour_date_id"]
    }
}


# -------------------------------------------------------------------------- #
#  FUNCTION EXECUTION LAYER — optimized, validated, token-efficient
# -------------------------------------------------------------------------- #

def execute_register_user(db, args: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta el registro real en SQLite."""

    # Clean & normalize values
    raw_name = args["name"].strip()
    name_parts = raw_name.split()
    first_name = name_parts[0]
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    email = args["email"].strip().lower()
    phone = args["phone"].strip()

    # Validate tour ID
    tours = list_active_tours(db)
    tour = next((t for t in tours if t.id == args["tour_date_id"]), None)
    if not tour:
        return {"status": "error", "message": "tour_date_id inválido"}

    # Parse grades
    grades_raw = args.get("grades", [])
    grades_list = [
        g.strip() for g in grades_raw
        if isinstance(g, str) and g.strip()
    ]
    grade_interest = ", ".join(grades_list) or "sin especificar"

    # Waitlist logic
    course_status = reserve_course_interest(db, grades_list)
    force_wait = course_status.get("wait_listed", False)

    # Create registration in DB
    try:
        reg, wait_listed = create_registration(
            db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            grade_interest=grade_interest,
            tour_date=tour,
            force_wait_listed=force_wait
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Return minimal, clean response
    return {
        "status": "success",
        "registration_id": reg.id,
        "wait_listed": wait_listed,
        "tour_date": str(tour.date)
    }
