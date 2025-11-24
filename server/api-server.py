import os
import sys
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.redbook import (  # noqa: E402
    get_note_content,
    login_action,
    search_notes,
    shutdown_browser,
)


class SearchRequest(BaseModel):
    keywords: str = Field(..., description="搜索关键词")
    limit: int = Field(default=30, ge=1, le=100, description="返回结果数量限制")


class SearchResponse(BaseModel):
    success: bool
    data: List[Dict[str, str]]
    message: str = ""


class NoteContentRequest(BaseModel):
    url: str = Field(..., description="笔记URL")


class NoteContentResponse(BaseModel):
    success: bool
    data: str = ""
    message: str = ""


class LoginResponse(BaseModel):
    success: bool
    message: str = ""


app = FastAPI(
    title="小红书搜索MCP服务",
    description="提供小红书笔记搜索和内容获取的API服务",
    version="1.0.0",
)


@app.on_event("shutdown")
async def cleanup_browser():
    await shutdown_browser()


@app.get("/")
async def root():
    return {
        "name": "小红书搜索MCP服务",
        "version": "1.0.0",
        "endpoints": {
            "login": "/api/login",
            "search": "/api/search",
            "note_content": "/api/note-content",
            "health": "/api/health",
        },
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "xiaohongshu_scraper"}


@app.post("/api/login", response_model=LoginResponse)
async def api_login():
    try:
        result = await login_action()
        return LoginResponse(success=True, message=result)
    except Exception as e:
        logger.error(f"登录API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@app.post("/api/search", response_model=SearchResponse)
async def api_search(request: SearchRequest):
    try:
        result = await search_notes(request.keywords, request.limit)
        if isinstance(result, list):
            return SearchResponse(
                success=True,
                data=result,
                message=f"成功搜索到 {len(result)} 条结果",
            )

        return SearchResponse(success=False, data=[], message=str(result))
    except Exception as e:
        logger.error(f"搜索API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@app.post("/api/note-content", response_model=NoteContentResponse)
async def api_get_note_content(request: NoteContentRequest):
    try:
        result = await get_note_content(request.url)
        return NoteContentResponse(
            success=True,
            data=result,
            message="成功获取笔记内容",
        )
    except Exception as e:
        logger.error(f"获取笔记内容API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取笔记内容失败: {str(e)}")


def run_fastapi_server():
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    run_fastapi_server()
