"""SQLite helpers for tour registrations without external ORM dependencies."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator, List, Optional, Tuple

DATABASE_PATH = Path("tour.db")

ORDINAL_KEYWORDS = {
    "primera": 1,
    "primer": 1,
    "segunda": 2,
    "segundo": 2,
    "tercera": 3,
    "tercer": 3,
    "cuarta": 4,
    "cuarto": 4,
    "quinta": 5,
    "quinto": 5,
}


@dataclass
class TourDate:
    id: int
    date: date
    capacity: int
    registered: int
    status: str

    @property
    def available_slots(self) -> int:
        return max(self.capacity - self.registered, 0)


@dataclass
class Registration:
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    grade_interest: str
    tour_date_id: int
    wait_listed: bool


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed_days: int = 4) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tour_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                capacity INTEGER NOT NULL DEFAULT 12,
                registered INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                grade_interest TEXT NOT NULL,
                tour_date_id INTEGER NOT NULL,
                wait_listed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(tour_date_id) REFERENCES tour_dates(id)
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM tour_dates").fetchone()[0]
        if count == 0:
            today = date.today()
            for offset in range(1, seed_days + 1):
                day = today + timedelta(days=offset * 3)
                conn.execute(
                    "INSERT INTO tour_dates(date, capacity, registered, status) VALUES (?, ?, 0, 'open')",
                    (day.isoformat(), 12 if offset % 2 == 0 else 10),
                )
        conn.commit()
    finally:
        conn.close()


def get_db_session() -> Generator[sqlite3.Connection, None, None]:
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _row_to_tour(row: sqlite3.Row) -> TourDate:
    return TourDate(
        id=row["id"],
        date=datetime.fromisoformat(row["date"]).date(),
        capacity=row["capacity"],
        registered=row["registered"],
        status=row["status"],
    )


def list_active_tours(conn: sqlite3.Connection) -> List[TourDate]:
    rows = conn.execute(
        "SELECT * FROM tour_dates WHERE status != 'closed' ORDER BY date ASC"
    ).fetchall()
    return [_row_to_tour(row) for row in rows]


def find_tour_by_input(conn: sqlite3.Connection, user_choice: str) -> Optional[TourDate]:
    user_choice = user_choice.strip().lower()
    tours = list_active_tours(conn)
    if not tours:
        return None

    if user_choice.isdigit():
        idx = int(user_choice) - 1
        if 0 <= idx < len(tours):
            return tours[idx]

    for keyword, index in ORDINAL_KEYWORDS.items():
        if keyword in user_choice:
            idx = index - 1
            if 0 <= idx < len(tours):
                return tours[idx]

    for tour in tours:
        options = [
            tour.date.strftime("%d/%m/%Y"),
            tour.date.strftime("%Y-%m-%d"),
            tour.date.strftime("%d/%m"),
            str(tour.date.day),
        ]
        if any(opt.startswith(user_choice) for opt in options):
            return tour
    return None


def _row_to_registration(row: sqlite3.Row) -> Registration:
    return Registration(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        phone=row["phone"],
        grade_interest=row["grade_interest"],
        tour_date_id=row["tour_date_id"],
        wait_listed=bool(row["wait_listed"]),
    )


def create_registration(
    conn: sqlite3.Connection,
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    grade_interest: str,
    tour_date: TourDate,
    force_wait_listed: bool = False,
) -> Tuple[Registration, bool]:
    """Persist a registration and optionally force the wait-list flag.

    Even cuando los tours tienen cupos, ciertos grados se manejan con lista
    prioritaria. `force_wait_listed` permite reflejar ese estado sin depender
    únicamente de la capacidad del tour.
    """

    wait_listed = force_wait_listed
    new_registered = tour_date.registered + 1

    status = tour_date.status
    conn.execute(
        "UPDATE tour_dates SET registered = ?, status = ? WHERE id = ?",
        (new_registered, status, tour_date.id),
    )
    registration_cursor = conn.execute(
        """
        INSERT INTO registrations(first_name, last_name, email, phone, grade_interest, tour_date_id, wait_listed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (first_name, last_name, email, phone, grade_interest, tour_date.id, int(wait_listed)),
    )
    conn.commit()
    reg_id = registration_cursor.lastrowid
    row = conn.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    return _row_to_registration(row), wait_listed
