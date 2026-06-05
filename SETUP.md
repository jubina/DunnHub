# Setup Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (for remote access)
- [Ollama](https://ollama.ai/) with `mistral-nemo:12b` (for local LLM routing, optional)

---

## 1. Clone and install dependencies

```bash
git clone https://github.com/jubina/DunnHub.git
cd DunnHub
uv install   # or: pip install -r requirements.txt
```

---

## 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
DUNNHUB_API_KEY=   # generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
OAUTH_PASSWORD=    # a strong password for the auth page
OAUTH_SECRET=      # generate: python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Initialize the database

The database path is set in `database.py`:
```python
DB_PATH = Path(r"C:\DunnHub\db\dunnhub.db")
```

Change this to any path you prefer. The directory will be created automatically on first use.

---

## 4. Run the local server (Claude Desktop)

```bash
python server.py
```

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dunnhub": {
      "command": "python",
      "args": ["C:/path/to/DunnHub/server.py"]
    }
  }
}
```

---

## 5. Run the remote server (claude.ai / mobile)

```bash
uv run uvicorn remote_server:app --host 127.0.0.1 --port 8000
```

Then point a Cloudflare Tunnel at `localhost:8000`.

Add to claude.ai MCP settings:
```
URL: https://your-tunnel-domain/mcp
Auth: Bearer <your DUNNHUB_API_KEY>
```

---

## 6. (Optional) Local LLM via Ollama

```bash
ollama pull mistral-nemo:12b
ollama serve
```

The `ask_ollama` tool in the remote server will route tasks to it automatically.
