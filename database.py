"""
database.py — DunnHub Project OS
SQLite interface layer. All SQL lives here. server.py never touches SQL directly.
"""

import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Path to the database ────────────────────────────────────────────────────
DB_PATH = Path(r"C:\DunnHub\db\dunnhub.db")


def _connect() -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and row factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Projects ─────────────────────────────────────────────────────────────────

def get_all_projects() -> list[dict]:
    """Return all projects ordered by status (active first) then name."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM projects
            ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END, name
        """).fetchall()
    return [dict(r) for r in rows]


def get_project(name: str) -> Optional[dict]:
    """Return a single project by slug name, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
    return dict(row) if row else None


def create_project(name: str, description: str) -> dict:
    """Create a new project. Returns the created row."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description)
        )
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
    return dict(row)


def update_project_status(name: str, status: str) -> None:
    """Update project status. Valid: active | paused | complete | abandoned."""
    valid = {"active", "paused", "complete", "abandoned"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")
    with _connect() as conn:
        conn.execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE name = ?",
            (status, datetime.now().isoformat(), name)
        )


# ── Sessions ─────────────────────────────────────────────────────────────────

def start_session(project_name: str) -> dict:
    """Open a new session for a project. Returns the session row."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found.")
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (project_id) VALUES (?)",
            (project["id"],)
        )
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def end_session(session_id: int, summary: str) -> None:
    """Close a session with a summary written by Claude."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
            (datetime.now().isoformat(), summary, session_id)
        )


def get_recent_sessions(project_name: str, limit: int = 5) -> list[dict]:
    """Return the most recent N sessions for a project."""
    project = get_project(project_name)
    if not project:
        return []
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM sessions
            WHERE project_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (project["id"], limit)).fetchall()
    return [dict(r) for r in rows]


# ── Context ───────────────────────────────────────────────────────────────────

def get_context(project_name: str) -> Optional[dict]:
    """Return the current context bookmark for a project."""
    project = get_project(project_name)
    if not project:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM context WHERE project_id = ?", (project["id"],)
        ).fetchone()
    return dict(row) if row else None


def update_context(
    project_name: str,
    current_brick: str,
    current_step: str,
    next_action: str,
    open_questions: str = ""
) -> None:
    """Upsert the context bookmark for a project."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found.")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO context (project_id, current_brick, current_step, next_action, open_questions, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                current_brick  = excluded.current_brick,
                current_step   = excluded.current_step,
                next_action    = excluded.next_action,
                open_questions = excluded.open_questions,
                last_updated   = excluded.last_updated
        """, (
            project["id"],
            current_brick,
            current_step,
            next_action,
            open_questions,
            datetime.now().isoformat()
        ))


# ── Decisions ─────────────────────────────────────────────────────────────────

def log_decision(
    project_name: str,
    decision: str,
    reasoning: str,
    session_id: Optional[int] = None
) -> None:
    """Log an architectural or strategic decision with its reasoning."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found.")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO decisions (project_id, session_id, decision, reasoning) VALUES (?, ?, ?, ?)",
            (project["id"], session_id, decision, reasoning)
        )


def get_decisions(project_name: str, limit: int = 10) -> list[dict]:
    """Return recent decisions for a project, newest first."""
    project = get_project(project_name)
    if not project:
        return []
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM decisions
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (project["id"], limit)).fetchall()
    return [dict(r) for r in rows]


# ── Data ──────────────────────────────────────────────────────────────────────

def store_data(project_name: str, data_type: str, data_key: str, data_value: str) -> None:
    """Upsert a key/value data entry for a project."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found.")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO data (project_id, data_type, data_key, data_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id, data_type, data_key) DO UPDATE SET
                data_value = excluded.data_value,
                created_at = excluded.created_at
        """, (project["id"], data_type, data_key, data_value))


def get_data(project_name: str, data_type: str, data_key: str) -> Optional[str]:
    """Retrieve a single data value by project, type, and key."""
    project = get_project(project_name)
    if not project:
        return None
    with _connect() as conn:
        row = conn.execute("""
            SELECT data_value FROM data
            WHERE project_id = ? AND data_type = ? AND data_key = ?
        """, (project["id"], data_type, data_key)).fetchone()
    return row["data_value"] if row else None


def list_data(project_name: str, data_type: Optional[str] = None) -> list[dict]:
    """List all data entries for a project, optionally filtered by type."""
    project = get_project(project_name)
    if not project:
        return []
    with _connect() as conn:
        if data_type:
            rows = conn.execute("""
                SELECT data_type, data_key, data_value, created_at FROM data
                WHERE project_id = ? AND data_type = ?
                ORDER BY data_type, data_key
            """, (project["id"], data_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT data_type, data_key, data_value, created_at FROM data
                WHERE project_id = ?
                ORDER BY data_type, data_key
            """, (project["id"],)).fetchall()
    return [dict(r) for r in rows]


# ── Full project brief (what Claude loads at session start) ───────────────────

def get_project_brief(project_name: str) -> dict:
    """
    Aggregate everything Claude needs to resume a project.
    This is the primary tool called at the start of every session.
    Returns: project metadata, current context, recent sessions, recent decisions.
    """
    project = get_project(project_name)
    if not project:
        return {"error": f"Project '{project_name}' not found."}

    return {
        "project":          project,
        "context":          get_context(project_name),
        "recent_sessions":  get_recent_sessions(project_name, limit=3),
        "recent_decisions": get_decisions(project_name, limit=5),
    }


# ── Filesystem ────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """Read and return the full contents of a file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return p.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> None:
    """Write content to a file, creating parent directories if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def list_directory(path: str) -> list[str]:
    """List all files and folders in a directory."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    return [str(item) for item in sorted(p.iterdir())]


# ── Command execution ─────────────────────────────────────────────────────────

def run_command(command: str, cwd: Optional[str] = None, timeout: int = 60) -> dict:
    """
    Execute a shell command and return stdout, stderr, and return code.
    command: full command string to run
    cwd: working directory — always specify explicitly, never rely on default
    timeout: seconds before giving up (default 60)
    """
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "success": result.returncode == 0
    }


# ── Migrations ────────────────────────────────────────────────────────────────

def run_migration(sql: str) -> str:
    """
    Execute raw DDL SQL against dunnhub.db.
    Used for schema changes — CREATE TABLE, ALTER TABLE, etc.
    Returns a success message or raises on error.
    """
    with _connect() as conn:
        conn.executescript(sql)
    return "Migration executed successfully."


def get_table_info() -> list[dict]:
    """
    Return all user-created tables and their column definitions.
    Useful for auditing the current schema.
    """
    with _connect() as conn:
        tables = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        result = []
        for table in tables:
            table_name = table["name"]
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            result.append({
                "table": table_name,
                "columns": [dict(c) for c in columns]
            })
    return result


# ── Workout Domain ────────────────────────────────────────────────────────────

def log_workout_session(
    performed_at: str,
    session_type: str,
    trainer_present: bool = False,
    notes: str = ""
) -> dict:
    """
    Create a new workout session row.
    performed_at: ISO date string of when the workout actually happened e.g. '2026-05-14'
    session_type: 'push' | 'pull' | 'legs' | 'cardio' | 'other'
    Returns the created session row including its id.
    """
    with _connect() as conn:
        cursor = conn.execute("""
            INSERT INTO workout_sessions (performed_at, session_type, trainer_present, notes)
            VALUES (?, ?, ?, ?)
        """, (performed_at, session_type, int(trainer_present), notes))
        row = conn.execute(
            "SELECT * FROM workout_sessions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def log_workout_exercise(
    session_id: int,
    exercise_name: str,
    muscle_group: str = "",
    equipment: str = "",
    order_in_session: int = 1
) -> dict:
    """
    Add an exercise to a workout session.
    Returns the created exercise row including its id.
    """
    with _connect() as conn:
        cursor = conn.execute("""
            INSERT INTO workout_exercises (session_id, exercise_name, muscle_group, equipment, order_in_session)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, exercise_name, muscle_group, equipment, order_in_session))
        row = conn.execute(
            "SELECT * FROM workout_exercises WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def log_workout_set(
    exercise_id: int,
    set_num: int,
    weight_lbs: Optional[float],
    reps: Optional[float],
    notes: str = ""
) -> dict:
    """
    Add a set to a workout exercise.
    weight_lbs: None for bodyweight exercises
    reps: float to handle 8.5, 7.5 etc. Notes field captures '+2 negatives' etc.
    Returns the created set row.
    """
    with _connect() as conn:
        cursor = conn.execute("""
            INSERT INTO workout_sets (exercise_id, set_num, weight_lbs, reps, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (exercise_id, set_num, weight_lbs, reps, notes))
        row = conn.execute(
            "SELECT * FROM workout_sets WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def get_workout_sessions(limit: int = 20) -> list[dict]:
    """Return recent workout sessions, newest first."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM workout_sessions
            ORDER BY performed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_workout_detail(session_id: int) -> dict:
    """
    Return a full workout session with all exercises and sets nested.
    """
    with _connect() as conn:
        session = conn.execute(
            "SELECT * FROM workout_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            return {"error": f"Session {session_id} not found."}

        exercises = conn.execute("""
            SELECT * FROM workout_exercises
            WHERE session_id = ?
            ORDER BY order_in_session
        """, (session_id,)).fetchall()

        result = dict(session)
        result["exercises"] = []
        for ex in exercises:
            ex_dict = dict(ex)
            sets = conn.execute("""
                SELECT * FROM workout_sets
                WHERE exercise_id = ?
                ORDER BY set_num
            """, (ex["id"],)).fetchall()
            ex_dict["sets"] = [dict(s) for s in sets]
            result["exercises"].append(ex_dict)

    return result


def get_exercise_history(exercise_name: str) -> list[dict]:
    """
    Return all sets for a given exercise across all sessions, ordered by date.
    Used for progress tracking — 'show me all my lat pulldown sets over time.'
    """
    with _connect() as conn:
        rows = conn.execute("""
            SELECT
                ws.performed_at,
                ws.session_type,
                ws.trainer_present,
                we.exercise_name,
                wset.set_num,
                wset.weight_lbs,
                wset.reps,
                wset.notes
            FROM workout_sets wset
            JOIN workout_exercises we ON wset.exercise_id = we.id
            JOIN workout_sessions ws ON we.session_id = ws.id
            WHERE LOWER(we.exercise_name) = LOWER(?)
            ORDER BY ws.performed_at ASC, wset.set_num ASC
        """, (exercise_name,)).fetchall()
    return [dict(r) for r in rows]
