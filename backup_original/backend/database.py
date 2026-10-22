
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "energy.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _columns(conn, table_name):
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def init_db():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                google_sub TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS energy_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reading_date TEXT NOT NULL,
                appliance TEXT NOT NULL DEFAULT 'Whole House',
                previous_reading REAL,
                current_reading REAL,
                kwh REAL NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, reading_date),
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
        """)

        # Safe migration for databases created by an older version.
        cols = _columns(conn, "app_users")
        if "google_sub" not in cols:
            conn.execute("ALTER TABLE app_users ADD COLUMN google_sub TEXT")
        if "password_hash" not in cols:
            conn.execute("ALTER TABLE app_users ADD COLUMN password_hash TEXT")
        if "created_at" not in cols:
            conn.execute(
                "ALTER TABLE app_users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
            )

        cols = _columns(conn, "energy_readings")
        if "appliance" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings "
                "ADD COLUMN appliance TEXT NOT NULL DEFAULT 'Whole House'"
            )
        if "previous_reading" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings ADD COLUMN previous_reading REAL"
            )
        if "current_reading" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings ADD COLUMN current_reading REAL"
            )
        if "kwh" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings ADD COLUMN kwh REAL NOT NULL DEFAULT 0"
            )
        if "cost" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings ADD COLUMN cost REAL NOT NULL DEFAULT 0"
            )
        if "created_at" not in cols:
            conn.execute(
                "ALTER TABLE energy_readings ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
            )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_energy_user_date
            ON energy_readings(user_id, reading_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_energy_user_created
            ON energy_readings(user_id, created_at)
        """)
        conn.commit()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM app_users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM app_users WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_google_sub(google_sub):
    conn = get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM app_users WHERE google_sub = ?", (google_sub,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password_hash=None, google_sub=None):
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute("""
            INSERT INTO app_users
                (name, email, password_hash, google_sub, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, password_hash, google_sub, now))
        conn.commit()
        return get_user_by_id(cur.lastrowid)
    finally:
        conn.close()


def link_google_account(user_id, google_sub):
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE app_users SET google_sub = ? WHERE id = ?",
            (google_sub, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_reading_by_date(user_id, reading_date):
    conn = get_db_connection()
    try:
        return conn.execute("""
            SELECT * FROM energy_readings
            WHERE user_id = ? AND reading_date = ?
        """, (user_id, reading_date)).fetchone()
    finally:
        conn.close()


def get_latest_reading_before(user_id, reading_date):
    conn = get_db_connection()
    try:
        return conn.execute("""
            SELECT * FROM energy_readings
            WHERE user_id = ? AND reading_date < ?
            ORDER BY reading_date DESC, id DESC
            LIMIT 1
        """, (user_id, reading_date)).fetchone()
    finally:
        conn.close()


def get_reading_by_id(user_id, reading_id):
    conn = get_db_connection()
    try:
        return conn.execute("""
            SELECT * FROM energy_readings
            WHERE id = ? AND user_id = ?
        """, (reading_id, user_id)).fetchone()
    finally:
        conn.close()


def save_or_update_reading(
    user_id,
    reading_date,
    appliance,
    previous_reading,
    current_reading,
    kwh,
    cost,
):
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat(timespec="seconds")
        existing = conn.execute("""
            SELECT id FROM energy_readings
            WHERE user_id = ? AND reading_date = ?
        """, (user_id, reading_date)).fetchone()

        if existing:
            conn.execute("""
                UPDATE energy_readings
                SET appliance = ?,
                    previous_reading = ?,
                    current_reading = ?,
                    kwh = ?,
                    cost = ?,
                    created_at = ?
                WHERE id = ?
            """, (
                appliance, previous_reading, current_reading,
                kwh, cost, now, existing["id"]
            ))
            reading_id = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO energy_readings
                    (user_id, reading_date, appliance, previous_reading,
                     current_reading, kwh, cost, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, reading_date, appliance, previous_reading,
                current_reading, kwh, cost, now
            ))
            reading_id = cur.lastrowid

        conn.commit()
        return get_reading_by_id(user_id, reading_id)
    finally:
        conn.close()


def get_readings(user_id, start_date=None, end_date=None, limit=100):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM energy_readings WHERE user_id = ?"
        params = [user_id]

        if start_date:
            query += " AND reading_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND reading_date <= ?"
            params.append(end_date)

        query += " ORDER BY reading_date DESC, id DESC LIMIT ?"
        params.append(int(limit))

        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def delete_reading(user_id, reading_id):
    conn = get_db_connection()
    try:
        cur = conn.execute("""
            DELETE FROM energy_readings
            WHERE id = ? AND user_id = ?
        """, (reading_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
