import os
import sys
from typing import Dict, List

from fastmcp import FastMCP
from loguru import logger

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.redbook import (  # noqa: E402
    get_note_content as redbook_get_note_content,
    login_action,
    search_notes as redbook_search_notes,
)


MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")
MCP_STREAM_HOST = os.getenv("MCP_STREAM_HOST", "0.0.0.0")
MCP_STREAM_PORT = int(os.getenv("MCP_STREAM_PORT", "8080"))

mcp = FastMCP("xiaohongshu_scraper")


@mcp.tool(name="login")
async def login() -> str:
    return await login_action()


@mcp.tool()
async def search_notes(keywords: str, limit: int = 30) -> List[Dict[str, str]]:
    return await redbook_search_notes(keywords, limit)


@mcp.tool()
async def get_note_content(url: str) -> str:
    return await redbook_get_note_content(url)


def run_mcp_server():
    logger.info(
        f"启动MCP服务器 (transport={MCP_TRANSPORT}, host={MCP_STREAM_HOST}, port={MCP_STREAM_PORT})..."
    )
    mcp.run(transport=MCP_TRANSPORT, host=MCP_STREAM_HOST, port=MCP_STREAM_PORT)


if __name__ == "__main__":
    run_mcp_server()
