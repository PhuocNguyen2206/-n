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
            CREATE TABLE IF NOT EXISTS vehicle_sessions (
              id TEXT PRIMARY KEY,
              vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
              entry_event_id TEXT NOT NULL REFERENCES access_events(id),
              entered_at TEXT NOT NULL,
              exited_at TEXT,
              status TEXT NOT NULL DEFAULT 'open'
            );
            CREATE TABLE IF NOT EXISTS vehicle_session_people (
              session_id TEXT NOT NULL REFERENCES vehicle_sessions(id),
              person_id TEXT NOT NULL REFERENCES people(id),
              PRIMARY KEY (session_id, person_id)
            );
            CREATE TABLE IF NOT EXISTS gate_sessions (
              id TEXT PRIMARY KEY,
              plate_number TEXT NOT NULL,
              entry_event_id TEXT NOT NULL,
              entered_at TEXT NOT NULL,
              exited_at TEXT,
              status TEXT NOT NULL DEFAULT 'open'
            );
            CREATE TABLE IF NOT EXISTS gate_session_faces (
              session_id TEXT NOT NULL REFERENCES gate_sessions(id),
              embedding TEXT NOT NULL,
              confidence REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_access_events_plate ON access_events(plate_number);
            CREATE INDEX IF NOT EXISTS idx_vehicle_sessions_vehicle ON vehicle_sessions(vehicle_id, status);
            CREATE INDEX IF NOT EXISTS idx_gate_sessions_plate ON gate_sessions(plate_number, status);
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(people)")}
        if "face_embedding" not in columns:
            connection.execute("ALTER TABLE people ADD COLUMN face_embedding TEXT")
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(access_events)")}
        if "evidence_path" not in event_columns:
            connection.execute("ALTER TABLE access_events ADD COLUMN evidence_path TEXT")
        session_columns = {row[1] for row in connection.execute("PRAGMA table_info(gate_sessions)")}
        if "entry_evidence_path" not in session_columns:
            connection.execute("ALTER TABLE gate_sessions ADD COLUMN entry_evidence_path TEXT")
        if "exit_evidence_path" not in session_columns:
            connection.execute("ALTER TABLE gate_sessions ADD COLUMN exit_evidence_path TEXT")
        if "exit_event_id" not in session_columns:
            connection.execute("ALTER TABLE gate_sessions ADD COLUMN exit_event_id TEXT")


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
