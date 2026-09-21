import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATABASE_PATH = Path("data/vehicle_ai.db")


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS people (
              id TEXT PRIMARY KEY,
              full_name TEXT NOT NULL,
              campus_id TEXT NOT NULL UNIQUE,
              role TEXT NOT NULL DEFAULT 'student',
              face_token TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS vehicles (
              id TEXT PRIMARY KEY,
              plate_number TEXT NOT NULL UNIQUE,
              owner_id TEXT NOT NULL REFERENCES people(id),
              vehicle_type TEXT NOT NULL DEFAULT 'motorbike',
              active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS vehicle_authorizations (
              id TEXT PRIMARY KEY,
              vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
              borrower_id TEXT NOT NULL REFERENCES people(id),
              valid_from TEXT NOT NULL,
              valid_until TEXT NOT NULL,
              note TEXT
            );
            CREATE TABLE IF NOT EXISTS access_events (
              id TEXT PRIMARY KEY,
              occurred_at TEXT NOT NULL,
              direction TEXT NOT NULL,
              plate_number TEXT,
              person_id TEXT REFERENCES people(id),
              decision TEXT NOT NULL,
              reason TEXT NOT NULL,
              plate_confidence REAL,
              face_confidence REAL
            );
            """
        )


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
