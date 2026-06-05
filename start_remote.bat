@echo off
:: start_remote.bat — Launch DunnHub remote MCP server
:: Run this once manually or set as a Windows startup task
:: The server will be available at http://localhost:8000
:: Cloudflare Tunnel proxies it to https://mcp.wizardsword.page

cd /d C:\DunnHub\mcp\servers\dunnhub-core
uv run uvicorn remote_server:app --host 127.0.0.1 --port 8000 --log-level info
