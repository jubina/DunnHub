# DunnHub

Personal AI agent infrastructure and life operating system.

A production MCP (Model Context Protocol) server connecting Claude to a structured SQLite database covering every domain of my life: health, career, finances, algo trading, gaming, and goals. Built to surface information proactively and act on my behalf — not to be queried manually.

---

## What This Is

Most people use AI assistants reactively — they ask a question, they get an answer, context is lost. DunnHub inverts that. Every session starts with full situational awareness. Every decision is logged with reasoning. Every project has a persistent context bookmark that survives across sessions, devices, and model versions.

It's also a working demonstration of end-to-end agent architecture: tool design, authentication, database modeling, local LLM routing, and remote access — all built from scratch for real daily use.

---

## Architecture

```
Claude (claude.ai / Claude Desktop / Mobile)
           │
           │  MCP over HTTPS (remote) or stdio (local)
           │
    ┌──────▼───────────────────────────────┐
    │     FastMCP Server  (server.py)      │
    │     24 tools across 7 domains        │
    │                                      │
    │  ┌─────────────┐  ┌───────────────┐  │
    │  │  database.py │  │  auth layer   │  │
    │  │  SQL layer   │  │  token-based  │  │
    │  └──────┬──────┘  └───────────────┘  │
    └─────────┼────────────────────────────┘
              │
       ┌──────▼──────┐
       │  dunnhub.db  │  ← Single SQLite file, all domains
       └─────────────┘

Remote access stack:
  FastMCP HTTP server → Cloudflare Tunnel → Public HTTPS endpoint
  Enables full tool access from any device including mobile
```

---

## Tool Inventory (24 tools)

### Project Management
| Tool | Purpose |
|------|---------|
| `get_project_brief` | **Primary session-start tool.** Returns full project state: metadata, current brick/step, last 3 session summaries, last 5 decisions |
| `list_projects` | Overview of all projects and statuses |
| `create_project` | Initialize a new project |
| `update_project_status` | Set status: active / paused / complete / abandoned |

### Session Tracking
| Tool | Purpose |
|------|---------|
| `start_session` | Open a work session, returns session ID |
| `end_session` | Close session with a summary for future context |

### Context & Memory
| Tool | Purpose |
|------|---------|
| `update_context` | Save current brick, step, next action, and open questions |
| `log_decision` | Record architectural/strategic decisions with reasoning |
| `get_decisions` | Retrieve decision history for a project |

### Key/Value Data Store
| Tool | Purpose |
|------|---------|
| `store_data` | Persist any structured data under project/type/key |
| `get_data` | Retrieve a single value |
| `list_data` | Audit all stored data for a project |

### Filesystem
| Tool | Purpose |
|------|---------|
| `read_file` | Read any file on the local machine |
| `write_file` | Write files (creates directories as needed) |
| `list_directory` | Browse the local filesystem |

### Health & Fitness
| Tool | Purpose |
|------|---------|
| `log_workout_session` | Create a session (push/pull/legs/cardio) |
| `log_workout_exercise` | Add an exercise to a session |
| `log_workout_set` | Log sets with weight, reps, and notes |
| `get_workout_sessions` | Recent session history |
| `get_workout_detail` | Full session with all exercises and sets nested |
| `get_exercise_history` | Progress tracking for a specific exercise over time |

### Database & Admin
| Tool | Purpose |
|------|---------|
| `run_migration` | Execute DDL SQL for schema changes |
| `get_table_info` | Audit current schema |
| `check_server_status` | Verify server is alive, returns version + tool inventory |

---

## Domain Coverage

DunnHub's SQLite database spans multiple life domains, each queryable via natural language through the tool layer:

- **Projects & Career** — active projects, context bookmarks, decision logs, employment data
- **Health & Fitness** — Push/Pull/Legs workout tracking with progression history
- **Algo Trading** — feeds into the [Algo-Trading](https://github.com/jubina/Algo-Trading) bot (BTC/ETH pairs trading)
- **Gaming** — 7 Days to Die server state, base design decisions
- **Goals** — long-term objective tracking tied to project work

---

## Local LLM Integration

The remote server (`remote_server.py`) routes database and filesystem operations through a local Ollama instance (Mistral-Nemo 12B) rather than consuming Claude's context window for every operation. This is a deliberate architectural decision:

- Keeps cloud LLM context lean and reduces API costs
- Demonstrates model-agnostic design — the reasoning layer is swappable
- Local LLM handles structured data retrieval; Claude handles reasoning and synthesis

```
Claude (cloud) ──► high-level reasoning, synthesis, decisions
Ollama/Mistral  ──► DB queries, file ops, structured data retrieval
```

---

## Two Server Modes

| Mode | File | Transport | Used By |
|------|------|-----------|---------|
| Local | `server.py` | stdio | Claude Desktop (Windows) |
| Remote | `remote_server.py` | HTTPS via Cloudflare Tunnel | claude.ai, mobile, any device |

Both servers expose identical tools. The remote server adds token-based authentication.

---

## Stack

- **Python** — FastMCP, sqlite3, httpx
- **SQLite** — single-file database, all domains
- **Ollama** — local LLM runtime (Mistral-Nemo 12B)
- **Cloudflare Tunnel** — zero-config public HTTPS endpoint
- **Claude API** — remote reasoning layer

---

## Why I Built This

**Context loss kills long-running projects.** Most AI workflows start from scratch every session. DunnHub ensures that every session — regardless of device or model — starts with full project awareness.

**It's also an architecture demonstration.** Tool design, auth patterns, database modeling, local LLM routing, remote access infrastructure — this is what production agent systems actually look like, built by someone who needed it to work daily, not just in a demo.

---

## Setup

> Sanitized version — credentials and personal data removed. See `config.example.py` for required environment variables.

```bash
# Install dependencies
uv install   # or pip install -r requirements.txt

# Run local server (Claude Desktop)
python server.py

# Run remote server
python remote_server.py
```

---

## Related Projects

- [Algo-Trading](https://github.com/jubina/Algo-Trading) — BTC/ETH pairs trading bot that feeds trade data back into DunnHub
