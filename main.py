import multiprocessing
import os
import runpy
import signal
import sys
import time
from typing import Optional
from loguru import logger


logger.remove()
logger.level("DEBUG")
logger.add(
    sys.stdout,
    colorize=True,
    format="<g>{time:YYYY-MM-DD HH:mm:ss}</g> | {level} | {message}",
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(PROJECT_ROOT, "server")
API_SERVER_PATH = os.path.join(SERVER_DIR, "api-server.py")
MCP_SERVER_PATH = os.path.join(SERVER_DIR, "mcp-server.py")

fastapi_process: Optional[multiprocessing.Process] = None
mcp_process: Optional[multiprocessing.Process] = None


def run_fastapi_server_process():
    """在独立进程中执行 FastAPI 脚本"""
    logger.info("启动FastAPI服务器进程...")
    runpy.run_path(API_SERVER_PATH, run_name="__main__")


def run_mcp_server_process():
    """在独立进程中执行 MCP 脚本"""
    logger.info("启动MCP服务器进程...")
    runpy.run_path(MCP_SERVER_PATH, run_name="__main__")


def safe_terminate(proc: Optional[multiprocessing.Process], name: str):
    """安全终止进程的封装方法"""
    if proc is None:
        logger.debug(f"无需终止{name}进程：未初始化")
        return

    try:
        pid = proc.pid
        if pid is None:
            logger.debug(f"无需终止{name}进程：无有效PID")
            return

        if not proc.is_alive():
            logger.debug(f"无需终止{name}进程：进程已终止")
            return

        logger.info(f"正在停止{name}服务器 (PID: {pid})")
        proc.terminate()
        proc.join(timeout=5)

        if proc.exitcode is None:
            logger.warning(f"{name}进程未响应终止信号，执行强制终止")
            proc.kill()
            proc.join()
    except ValueError as e:
        if "not a child process" in str(e):
            logger.warning(f"无法终止{name}进程：非直接子进程")
        else:
            logger.error(f"终止{name}进程时出现值错误: {e}")
    except Exception as e:
        logger.error(f"终止{name}进程时发生意外错误: {repr(e)}")
    finally:
        try:
            proc.close()
        except Exception:
            pass


def signal_handler(sig, frame):
    logger.info(f"\n收到终止信号 {sig}，开始清理进程...")
    for proc, name in [(fastapi_process, "FastAPI"), (mcp_process, "MCP")]:
        safe_terminate(proc, name)
    sys.exit(0)


def main():
    global fastapi_process, mcp_process

    run_mode = os.getenv("RUN_MODE", "both")

    if run_mode in ["both", "api"]:
        fastapi_process = multiprocessing.Process(
            target=run_fastapi_server_process,
            name="FastAPI-Server",
            daemon=True,
        )
        fastapi_process.start()
        logger.info(f"FastAPI服务器已启动 (PID: {fastapi_process.pid})")

    if run_mode in ["both", "mcp"]:
        mcp_process = multiprocessing.Process(
            target=run_mcp_server_process,
            name="MCP-Server",
            daemon=True,
        )
        mcp_process.start()
        logger.info(f"MCP服务器已启动 (PID: {mcp_process.pid})")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            alive_processes = []
            for proc, name in [(fastapi_process, "FastAPI"), (mcp_process, "MCP")]:
                if proc and proc.is_alive():
                    alive_processes.append(name)

            if not alive_processes:
                logger.info("所有服务进程已停止")
                break

            time.sleep(1)
    except Exception as e:
        logger.critical(f"主进程异常: {repr(e)}")
        signal_handler(None, None)


if __name__ == "__main__":
    main()
