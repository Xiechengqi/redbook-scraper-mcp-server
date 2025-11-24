#!/usr/bin/env bash

source ~/.profile

git clone https://gh-proxy.com/https://github.com/Xiechengqi/redbook-scraper-mcp-server.git /app/redbook || exit 1
cd /app/redbook
uv venv
source .venv/bin/activate
uv run main.py
