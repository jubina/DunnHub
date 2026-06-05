"""
server.py — DunnHub Project OS
FastMCP server. Exposes database.py functions as tools Claude can call.
This is the file Claude Desktop runs. It never touches SQL directly.
"""

from mcp.server.fastmcp import FastMCP
import database as db

# ── Server instance ───────────────────────────────────────────────────────────
mcp = FastMCP(
    name="dunnhub",
    instructions="""
    You are connected to JR's DunnHub Project OS database.
    Use these tools at the start of every session to load project context.
    Use them at the end of every session to save progress.
    Never guess at project state — always read it from the database first.
    """
)


# ── Project tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> list[dict]:
    """
    List all projects with their current status.
    Call this when JR asks what we're working on or wants an overview.
    """
    return db.get_all_projects()


@mcp.tool()
def create_project(name: str, description: str) -> dict:
    """
    Create a new project in the database.
    name: short slug, lowercase, underscores (e.g. 'algo_trading')
    description: one sentence describing what this project is
    """
    return db.create_project(name, description)


@mcp.tool()
def update_project_status(name: str, status: str) -> str:
    """
    Update a project's status.
    Valid values: active | paused | complete | abandoned
    """
    db.update_project_status(name, status)
    return f"Project '{name}' status updated to '{status}'."


# ── Session tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def start_session(project_name: str) -> dict:
    """
    Open a new session for a project.
    Call this at the beginning of any focused work session.
    Returns the session row including its id — store this for end_session.
    """
    return db.start_session(project_name)


@mcp.tool()
def end_session(session_id: int, summary: str) -> str:
    """
    Close a session with a summary.
    Call this when JR says he's done for the day or switching projects.
    summary: 2-4 sentences describing what was accomplished and any loose ends.
    session_id: the id returned by start_session at the top of this session.
    """
    db.end_session(session_id, summary)
    return f"Session {session_id} closed and summarised."


# ── Context tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_project_brief(project_name: str) -> dict:
    """
    THE PRIMARY TOOL. Call this first at the start of every session.
    Returns everything needed to resume a project without reconstruction:
    - project metadata and status
    - current brick, step, and next action
    - last 3 session summaries
    - last 5 decisions with reasoning
    Use this to brief JR before asking what he wants to do.
    """
    return db.get_project_brief(project_name)


@mcp.tool()
def update_context(
    project_name: str,
    current_brick: str,
    current_step: str,
    next_action: str,
    open_questions: str = ""
) -> str:
    """
    Update the context bookmark for a project.
    Call this whenever meaningful progress is made, not just at session end.
    current_brick: e.g. 'Brick 2'
    current_step: e.g. 'server.py written, config.json next'
    next_action: the single most important next thing to do
    open_questions: anything unresolved that future-Claude should know about
    """
    db.update_context(project_name, current_brick, current_step, next_action, open_questions)
    return f"Context updated for '{project_name}'."


# ── Decision tools ────────────────────────────────────────────────────────────

@mcp.tool()
def log_decision(
    project_name: str,
    decision: str,
    reasoning: str,
    session_id: int = None
) -> str:
    """
    Log an architectural or strategic decision with its reasoning.
    Call this whenever a real choice is made — not every micro-decision,
    but anything future-Claude would wonder 'why did we do it this way?'
    decision: what was decided (one sentence)
    reasoning: why (this is the gold — be specific)
    """
    db.log_decision(project_name, decision, reasoning, session_id)
    return f"Decision logged for '{project_name}'."


@mcp.tool()
def get_decisions(project_name: str, limit: int = 10) -> list[dict]:
    """
    Return recent decisions for a project.
    Useful when JR asks why something was done a certain way.
    """
    return db.get_decisions(project_name, limit)


# ── Data tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def store_data(
    project_name: str,
    data_type: str,
    data_key: str,
    data_value: str
) -> str:
    """
    Store a key/value data entry for a project.
    data_type: category label e.g. 'config', 'result', 'reference', 'backtest'
    data_key: unique identifier within that type e.g. 'ticker_pair', 'sharpe_ratio'
    data_value: the value as a string — JSON is fine for complex data
    """
    db.store_data(project_name, data_type, data_key, data_value)
    return f"Stored '{data_key}' under '{data_type}' for '{project_name}'."


@mcp.tool()
def get_data(project_name: str, data_type: str, data_key: str) -> str:
    """
    Retrieve a single data value by project, type, and key.
    Returns None if not found.
    """
    result = db.get_data(project_name, data_type, data_key)
    return result if result is not None else f"No data found for key '{data_key}'."


@mcp.tool()
def list_data(project_name: str, data_type: str = None) -> list[dict]:
    """
    List all stored data for a project, optionally filtered by type.
    Useful for auditing what's been stored across sessions.
    """
    return db.list_data(project_name, data_type)


# ── Filesystem tools ──────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str) -> str:
    """
    Read and return the full contents of a file on the local machine.
    path: absolute Windows path e.g. 'C:\\DunnHub\\mcp\\servers\\dunnhub-core\\server.py'
    """
    return db.read_file(path)


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """
    Write content to a file on the local machine.
    Creates parent directories if they don't exist.
    Overwrites if the file already exists.
    path: absolute Windows path
    content: full file content as a string
    """
    db.write_file(path, content)
    return f"File written: {path}"


@mcp.tool()
def list_directory(path: str) -> list[str]:
    """
    List all files and folders in a directory.
    path: absolute Windows path e.g. 'C:\\DunnHub\\'
    """
    return db.list_directory(path)


# ── Command execution ─────────────────────────────────────────────────────────

@mcp.tool()
def run_command(command: str, cwd: str = None, timeout: int = 60) -> dict:
    """
    Execute a shell command on the local machine and return the result.
    command: full command string e.g. 'uv add fastapi uvicorn'
    cwd: working directory — always specify the full absolute path
    timeout: seconds before giving up (default 60, use higher for installs)
    Returns: returncode, stdout, stderr, success (bool)
    """
    return db.run_command(command, cwd, timeout)


# ── Migration tools ───────────────────────────────────────────────────────────

@mcp.tool()
def run_migration(sql: str) -> str:
    """
    Execute raw DDL SQL against dunnhub.db.
    Use for schema changes: CREATE TABLE, ALTER TABLE, DROP TABLE etc.
    sql: full SQL string to execute — can contain multiple statements
    Returns a success message or raises on error.
    """
    return db.run_migration(sql)


@mcp.tool()
def get_table_info() -> list[dict]:
    """
    Return all tables in dunnhub.db with their column definitions.
    Use this to audit the current schema before writing migrations.
    """
    return db.get_table_info()


# ── Workout tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def log_workout_session(
    performed_at: str,
    session_type: str,
    trainer_present: bool = False,
    notes: str = ""
) -> dict:
    """
    Create a new workout session.
    performed_at: when the workout happened — ISO date e.g. '2026-05-14'
    session_type: 'push' | 'pull' | 'legs' | 'cardio' | 'other'
    trainer_present: True if this was a trainer session
    notes: trainer notes, context, observations
    Returns the session row including its id — needed for log_workout_exercise.
    """
    return db.log_workout_session(performed_at, session_type, trainer_present, notes)


@mcp.tool()
def log_workout_exercise(
    session_id: int,
    exercise_name: str,
    muscle_group: str = "",
    equipment: str = "",
    order_in_session: int = 1
) -> dict:
    """
    Add an exercise to a workout session.
    session_id: id returned by log_workout_session
    exercise_name: e.g. 'Lat Pulldowns', 'Low Cable Seated Rows'
    muscle_group: 'back' | 'biceps' | 'chest' | 'shoulders' | 'legs' | 'triceps'
    equipment: 'cable' | 'dumbbell' | 'barbell' | 'smith machine' | 'machine' | 'bodyweight'
    order_in_session: 1, 2, 3 — preserves exercise sequence
    Returns the exercise row including its id — needed for log_workout_set.
    """
    return db.log_workout_exercise(session_id, exercise_name, muscle_group, equipment, order_in_session)


@mcp.tool()
def log_workout_set(
    exercise_id: int,
    set_num: int,
    weight_lbs: float = None,
    reps: float = None,
    notes: str = ""
) -> dict:
    """
    Add a set to a workout exercise.
    exercise_id: id returned by log_workout_exercise
    set_num: 1, 2, 3
    weight_lbs: omit or None for bodyweight exercises
    reps: float — handles 8.5, 7.5 etc.
    notes: '+2 negatives', 'last rep sloppy', 'dropped for form' etc.
    """
    return db.log_workout_set(exercise_id, set_num, weight_lbs, reps, notes)


@mcp.tool()
def get_workout_sessions(limit: int = 20) -> list[dict]:
    """
    Return recent workout sessions, newest first.
    Use for overview and dashboard population.
    """
    return db.get_workout_sessions(limit)


@mcp.tool()
def get_workout_detail(session_id: int) -> dict:
    """
    Return a full workout session with all exercises and sets nested.
    Use to verify a logged session looks correct.
    """
    return db.get_workout_detail(session_id)


@mcp.tool()
def get_exercise_history(exercise_name: str) -> list[dict]:
    """
    Return all sets for a given exercise across all sessions, ordered by date.
    Use for progress tracking — 'show me all my lat pulldown sets over time.'
    exercise_name: case-insensitive match e.g. 'Lat Pulldowns'
    """
    return db.get_exercise_history(exercise_name)


# ── Server status ─────────────────────────────────────────────────────────────

SERVER_VERSION = "1.2.0"

@mcp.tool()
def check_server_status() -> dict:
    """
    Confirm the MCP server is alive and return version + tool inventory.
    Call this immediately after restarting Claude Desktop to verify the
    new server loaded correctly.
    """
    tools = [
        # Project tools
        "list_projects", "create_project", "update_project_status",
        # Session tools
        "start_session", "end_session",
        # Context tools
        "get_project_brief", "update_context",
        # Decision tools
        "log_decision", "get_decisions",
        # Data tools
        "store_data", "get_data", "list_data",
        # Filesystem tools
        "read_file", "write_file", "list_directory",
        # Command execution
        "run_command",
        # Migration tools
        "run_migration", "get_table_info",
        # Workout tools
        "log_workout_session", "log_workout_exercise", "log_workout_set",
        "get_workout_sessions", "get_workout_detail", "get_exercise_history",
        # Status
        "check_server_status",
    ]
    return {
        "status": "online",
        "version": SERVER_VERSION,
        "tool_count": len(tools),
        "tools": tools,
        "db_path": str(db.DB_PATH),
        "db_exists": db.DB_PATH.exists(),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
