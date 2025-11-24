#!/usr/bin/env bash

export PATH="$HOME/.local/bin:$PATH"

! ls /app/redbook &> /dev/null && git clone https://gh-proxy.com/https://github.com/Xiechengqi/redbook-scraper-mcp-server.git /app/redbook
cd /app/redbook
! ls .venv/bin/activate &> /dev/null && uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run main.py
