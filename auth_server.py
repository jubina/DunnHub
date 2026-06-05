"""
auth_server.py — DunnHub OAuth2 Authorization Server
Standalone OAuth2 provider for auth.wizardsword.page.

Implements the Authorization Code flow + dynamic client registration (RFC 7591).
Single-user personal server — no user database, just a password check.

Issued tokens are written to the shared token_store so remote_server.py can validate them.

Run with: uv run uvicorn auth_server:app --host 127.0.0.1 --port 8001 --log-level info
"""

import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import token_store

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

OAUTH_PASSWORD = os.getenv("OAUTH_PASSWORD")
OAUTH_SECRET   = os.getenv("OAUTH_SECRET")
API_KEY        = os.getenv("DUNNHUB_API_KEY")

if not OAUTH_PASSWORD:
    raise RuntimeError("OAUTH_PASSWORD not set in .env")
if not OAUTH_SECRET:
    raise RuntimeError("OAUTH_SECRET not set in .env")
if not API_KEY:
    raise RuntimeError("DUNNHUB_API_KEY not set in .env")

# Seed the permanent API key into the shared store on startup
token_store.store_token(API_KEY)

# ── In-memory stores ──────────────────────────────────────────────────────────
_auth_codes: dict[str, dict] = {}
_registered_clients: dict[str, dict] = {}

CODE_TTL = 300  # 5 minutes

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="DunnHub Auth Server", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dunnhub-auth"}


@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    base = "https://auth.wizardsword.page"
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
    }


@app.post("/register")
async def register_client(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    client_id = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)

    client_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_id_issued_at": int(time.time()),
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": body.get("grant_types", ["authorization_code"]),
        "response_types": body.get("response_types", ["code"]),
        "token_endpoint_auth_method": body.get("token_endpoint_auth_method", "none"),
        "client_name": body.get("client_name", "Unknown Client"),
    }

    _registered_clients[client_id] = client_data
    return JSONResponse(content=client_data, status_code=201)


LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DunnHub — Authorize</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
      background: #0d0d0d; font-family: 'Segoe UI', system-ui, sans-serif; color: #e0e0e0;
    }}
    .card {{
      background: #141414; border: 1px solid #2a2a2a; border-radius: 12px;
      padding: 2.5rem 2rem; width: 100%; max-width: 380px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }}
    .logo {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 0.25rem; color: #fff; }}
    .logo span {{ color: #7c6af7; }}
    .subtitle {{ font-size: 0.8rem; color: #666; margin-bottom: 2rem; }}
    label {{ display: block; font-size: 0.75rem; color: #888; margin-bottom: 0.4rem;
             letter-spacing: 0.05em; text-transform: uppercase; }}
    input[type="password"] {{
      width: 100%; padding: 0.65rem 0.85rem; background: #1e1e1e;
      border: 1px solid #333; border-radius: 8px; color: #fff;
      font-size: 0.95rem; outline: none; transition: border-color 0.15s; margin-bottom: 1.25rem;
    }}
    input[type="password"]:focus {{ border-color: #7c6af7; }}
    button {{
      width: 100%; padding: 0.7rem; background: #7c6af7; color: #fff;
      border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600;
      cursor: pointer; transition: background 0.15s;
    }}
    button:hover {{ background: #6a58e0; }}
    .error {{
      background: #2a1a1a; border: 1px solid #5a2a2a; color: #ff6b6b;
      border-radius: 8px; padding: 0.6rem 0.85rem; font-size: 0.85rem; margin-bottom: 1rem;
    }}
    .client-info {{ font-size: 0.75rem; color: #555; margin-top: 1.25rem; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">Dunn<span>Hub</span></div>
    <div class="subtitle">Personal command center</div>
    {error_block}
    <form method="POST" action="/authorize">
      <input type="hidden" name="client_id"     value="{client_id}">
      <input type="hidden" name="redirect_uri"  value="{redirect_uri}">
      <input type="hidden" name="state"         value="{state}">
      <input type="hidden" name="response_type" value="code">
      <label for="password">Password</label>
      <input type="password" id="password" name="password"
             autofocus autocomplete="current-password" placeholder="••••••••">
      <button type="submit">Authorize</button>
    </form>
    <div class="client-info">Authorizing: {client_id}</div>
  </div>
</body>
</html>
"""


@app.get("/authorize", response_class=HTMLResponse)
async def authorize_get(
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
):
    return LOGIN_PAGE.format(
        client_id=client_id, redirect_uri=redirect_uri,
        state=state, error_block="",
    )


@app.post("/authorize", response_class=HTMLResponse)
async def authorize_post(
    client_id:     str = Form(""),
    redirect_uri:  str = Form(""),
    state:         str = Form(""),
    response_type: str = Form("code"),
    password:      str = Form(""),
):
    if password != OAUTH_PASSWORD:
        error_block = '<div class="error">Incorrect password. Try again.</div>'
        return HTMLResponse(
            content=LOGIN_PAGE.format(
                client_id=client_id, redirect_uri=redirect_uri,
                state=state, error_block=error_block,
            ),
            status_code=401,
        )

    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "expires_at": time.time() + CODE_TTL,
    }

    params = {"code": code}
    if state:
        params["state"] = state

    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{separator}{urlencode(params)}",
        status_code=302,
    )


@app.post("/token")
async def token(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    grant_type = body.get("grant_type", "")
    if grant_type != "authorization_code":
        return JSONResponse(status_code=400, content={"error": "unsupported_grant_type"})

    code = body.get("code", "")
    code_data = _auth_codes.pop(code, None)

    if not code_data:
        return JSONResponse(status_code=400, content={"error": "invalid_grant", "error_description": "Unknown or already-used code."})

    if time.time() > code_data["expires_at"]:
        return JSONResponse(status_code=400, content={"error": "invalid_grant", "error_description": "Authorization code expired."})

    # Issue a fresh token and store it in the shared store
    access_token = secrets.token_urlsafe(32)
    token_store.store_token(access_token)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 315360000,
        "scope": "mcp",
    })
