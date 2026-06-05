"""
remote_server.py - DunnHub Remote MCP Server v3.2.0

Exposes DunnHub tools remotely over HTTPS via Cloudflare Tunnel.
Auth is handled by auth_server.py (auth.wizardsword.page).
This server validates tokens via the shared token_store module.

Run with: uv run uvicorn remote_server:app --host 127.0.0.1 --port 8000 --log-level info
Tunnel:   cloudflared tunnel run dunnhub
"""

import os
import httpx
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import token_store
import database as db

# -- Environment ---------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

API_KEY        = os.getenv("DUNNHUB_API_KEY")
SERVER_VERSION = "3.2.0"
OLLAMA_URL     = "http://localhost:11434"
OLLAMA_MODEL   = "mistral-nemo:12b"

if not API_KEY:
    raise RuntimeError("DUNNHUB_API_KEY not set in .env")

# Seed the permanent API key into token store on startup
token_store.store_token(API_KEY)


# -- MCP Server ----------------------------------------------------------------
mcp = FastMCP(
    name="dunnhub-remote",
    instructions="""
    You are connected to JR's DunnHub remote MCP server.
    Use check_server_status to confirm tools are live after any restart.
    run_command executes shell commands on JR's desktop.
    ask_ollama delegates tasks to the local Mistral model (mistral-nemo:12b).
    """
)


# -- Tools ---------------------------------------------------------------------

@mcp.tool()
def check_server_status() -> dict:
    """
    Confirm the remote MCP server is alive and return version + tool inventory.
    Call this at the start of every session to verify the server loaded correctly.
    """
    tools = ["check_server_status", "run_command", "ask_ollama", "update_project_status"]
    return {
        "status": "online",
        "version": SERVER_VERSION,
        "transport": "streamable-http",
        "endpoint": "https://mcp.wizardsword.page",
        "db_path": str(db.DB_PATH),
        "db_exists": db.DB_PATH.exists(),
    }


@mcp.tool()
def update_project_status(name: str, status: str) -> str:
    """
    Update a project's status.
    Valid values: active | paused | complete | abandoned
    """
    db.update_project_status(name, status)
    return f"Project '{name}' status updated to '{status}'."


@mcp.tool()
def run_command(command: str, cwd: str = None, timeout: int = 60) -> dict:
    """
    Execute a shell command on JR's desktop and return the result.
    command: full command string e.g. 'dir C:\\DunnHub'
    cwd: working directory - always use full absolute path
    timeout: seconds before giving up (default 60, use higher installs)
    Returns: returncode, stdout, stderr, success (bool)
    """
    return db.run_command(command, cwd, timeout)


@mcp.tool()
def ask_ollama(instruction: str) -> str:
    """
    Send a task to the local Ollama execution layer (mistral-nemo:12b).
    Use for tasks you want the local model to handle: DB queries, file ops,
    command execution, or any instruction Nemo should reason through locally.
    instruction: plain language instruction for Nemo to execute
    Returns: Nemo's response as a string
    """
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": instruction,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except httpx.ConnectError:
        return "ERROR: Could not connect to Ollama. Is it running? Check: ollama serve"
    except httpx.TimeoutException:
        return "ERROR: Ollama timed out after 120 seconds."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


# -- Token auth middleware ------------------------------------------------------
class TokenAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Bearer tokens on all /mcp requests.
    Tokens are checked against the shared token_store (tokens.json).
    Auth endpoints and health check are exempt.
    """
    EXEMPT_PATHS = {"/health", "/.well-known/oauth-authorization-server"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Let exempt paths through
        if path in self.EXEMPT_PATHS or path.startswith("/.well-known"):
            return await call_next(request)

        # Validate bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "Missing Bearer token"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if not token_store.is_valid(token):
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "Invalid or expired token"},
            )

        return await call_next(request)


# -- App assembly --------------------------------------------------------------
app = mcp.streamable_http_app()
app.add_middleware(TokenAuthMiddleware)
