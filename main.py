from typing import Any, List, Dict, Optional
import time
import asyncio
import json
import sys
from urllib.parse import quote
from loguru import logger
from playwright.async_api import async_playwright
from fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger.remove()
logger.level("DEBUG")
logger.add(
    sys.stdout,
    colorize=True,
    format="<g>{time:YYYY-MM-DD HH:mm:ss}</g> | {level} | {message}",
)

mcp = FastMCP("xiaohongshu_scraper")

# 创建FastAPI应用
app = FastAPI(
    title="小红书搜索MCP服务",
    description="提供小红书笔记搜索和内容获取的API服务",
    version="1.0.0"
)

# Pydantic模型定义
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

# 使用类来管理浏览器状态，避免全局变量问题
class BrowserManager:
    def __init__(self):
        self.browser_context = None
        self.main_page = None
        self.is_logged_in = False
        self.playwright = None
        self._lock = asyncio.Lock()

    async def ensure_browser(self):
        """确保浏览器已启动并登录"""
        async with self._lock:
            if self.browser_context is None:
                try:
                    self.playwright = await async_playwright().start()
                    # 连接到已存在的 Chrome 实例
                    playwright_instance = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
                    # 使用持久化上下文来保存用户状态
                    self.browser_context = playwright_instance.contexts[0]
                    logger.info("打开一个新标签页 ...")

                    # 查找当前所有有效页面
                    valid_pages = [p for p in self.browser_context.pages if not p.is_closed()]

                    if valid_pages:
                        self.main_page = valid_pages[0]
                        # 关闭其他无效/多余页面
                        for page in self.browser_context.pages[1:]:
                            if not page.is_closed():
                                await page.close()
                    else:
                        self.main_page = await self.browser_context.new_page()

                    self.main_page.set_default_timeout(60000)
                except Exception as e:
                    logger.error(f"浏览器初始化失败: {str(e)}")
                    raise

            # 确保页面有效性
            if not self.main_page or self.main_page.is_closed():
                self.main_page = await self.browser_context.new_page()

            # 检查登录状态
            if not self.is_logged_in:
                # 访问小红书首页
                try:
                    await self.main_page.goto("https://www.xiaohongshu.com", timeout=60000)
                    await asyncio.sleep(3)

                    # 尝试多种选择器查找登录元素
                    login_selector = [
                        'text="登录"',
                        'button:has-text("登录")',
                        'a:has-text("登录")'
                    ]
                    for selector in login_selector:
                        if await self.main_page.query_selector(selector):
                            return False
                    self.is_logged_in = True
                    return True
                except Exception as e:
                    logger.error(f"当前未登录 {str(e)}")
                    return False

            return True

    async def close(self):
        """关闭浏览器资源"""
        try:
            if self.browser_context:
                await self.browser_context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}")

# 创建浏览器管理器实例
browser_manager = BrowserManager()

def process_url(url: str) -> str:
    """处理URL，确保格式正确并保留所有参数

    Args:
        url: 原始URL

    Returns:
        str: 处理后的URL
    """
    processed_url = url.strip()

    # 移除可能的@符号前缀
    if processed_url.startswith('@'):
        processed_url = processed_url[1:]

    # 确保URL使用https协议
    if processed_url.startswith('http://'):
        processed_url = 'https://' + processed_url[7:]
    elif not processed_url.startswith('https://'):
        processed_url = 'https://' + processed_url

    # 如果URL不包含www.xiaohongshu.com，则添加它
    if 'xiaohongshu.com' in processed_url and 'www.xiaohongshu.com' not in processed_url:
        processed_url = processed_url.replace('xiaohongshu.com', 'www.xiaohongshu.com')

    return processed_url

@mcp.tool()
async def login() -> str:
    """登录小红书账号
    
    Returns:
        登录状态信息
    """
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if browser_manager.is_logged_in:
        return "已登录小红书账号"

    # 访问小红书登录页面
    if not browser_manager.main_page:
        return "浏览器初始化失败，请重试"

    await browser_manager.main_page.goto("https://www.xiaohongshu.com", timeout=60000)
    await asyncio.sleep(3)

    # 查找登录按钮并点击
    login_elements = await browser_manager.main_page.query_selector_all('text="登录"')
    if login_elements:
        await login_elements[0].click()

        # 提示用户手动登录
        message = "请在打开的浏览器窗口中完成登录操作。登录成功后，系统将自动继续。"

        # 等待用户登录成功
        max_wait_time = 180  # 等待3分钟
        wait_interval = 5
        waited_time = 0

        while waited_time < max_wait_time:
            # 检查是否已登录成功
            if not browser_manager.main_page:
                return "浏览器初始化失败，请重试"

            still_login = await browser_manager.main_page.query_selector_all('text="登录"')
            if not still_login:
                browser_manager.is_logged_in = True
                await asyncio.sleep(2)  # 等待页面加载
                return "登录成功！"

            # 继续等待
            await asyncio.sleep(wait_interval)
            waited_time += wait_interval

        return "登录等待超时。请重试或手动登录后再使用其他功能。"
    else:
        browser_manager.is_logged_in = True
        return "已登录小红书账号"

@mcp.tool()
async def search_notes(keywords: str, limit: int = 30) -> List[Dict[str, str]]:
    """根据关键词搜索半年内评论最多的图文笔记

    Args:
        keywords: 搜索关键词
        limit: 返回结果数量限制（默认30）
    
    Returns:
        包含笔记URL和标题的字典列表
    """
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        logger.error("请先登录小红书账号")
        return []

    if not browser_manager.main_page:
        logger.error("浏览器初始化失败，请重试")
        return []

    # 构建搜索URL并访问（对关键词进行URL编码）
    encoded_keywords = quote(keywords)
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keywords}"
    try:
        await browser_manager.main_page.goto(search_url, timeout=60000)
        # 检查网络请求是否完成（使用networkidle）
        await browser_manager.main_page.wait_for_load_state("networkidle")
        await (await browser_manager.main_page.wait_for_selector("//span[contains(text(), '筛选')]", state="visible")).hover()
        await asyncio.sleep(0.5)
        await (await browser_manager.main_page.wait_for_selector("//span[contains(text(), '最多评论')]", state="visible")).click()
        await asyncio.sleep(0.5)
        await (await browser_manager.main_page.wait_for_selector("//span[contains(text(), '图文')]", state="visible")).click()
        await asyncio.sleep(0.5)
        await (await browser_manager.main_page.wait_for_selector("//span[contains(text(), '半年内')]", state="visible")).click()
        await asyncio.sleep(0.5)
        await (await browser_manager.main_page.wait_for_selector("//span[contains(text(), '筛选')]", state="visible")).click()
        await asyncio.sleep(0.5)

        # 打印页面HTML用于调试
        page_html = await browser_manager.main_page.content()
        logger.info(f"页面HTML片段: {page_html[10000:10500]}...")

        # 使用更精确的选择器获取帖子卡片
        logger.info("尝试获取帖子卡片...")
        if not browser_manager.main_page:
            logger.error("浏览器初始化失败，请重试")
            return []

        post_cards = await browser_manager.main_page.query_selector_all('section.note-item')
        logger.info(f"找到 {len(post_cards)} 个帖子卡片")

        if not post_cards:
            # 尝试备用选择器
            if not browser_manager.main_page:
                logger.error("浏览器初始化失败，请重试")
                return []

            post_cards = await browser_manager.main_page.query_selector_all('div[data-v-a264b01a]')
            logger.info(f"使用备用选择器找到 {len(post_cards)} 个帖子卡片")

        post_links = []
        post_titles = []

        for card in post_cards:
            try:
                # 获取链接
                link_element = await card.query_selector('a[href*="/search_result/"]') if card else None
                if not link_element:
                    continue

                href = await link_element.get_attribute('href')
                if href and '/search_result/' in href:
                    # 构建完整URL
                    if href.startswith('/'):
                        full_url = f"https://www.xiaohongshu.com{href}"
                    else:
                        full_url = href

                    post_links.append(full_url)

                    # 尝试获取帖子标题
                    try:
                        # 打印卡片HTML用于调试
                        card_html = await card.inner_html() if card else ""
                        # logger.info(f"卡片HTML片段: {card_html[:300]}...")

                        # 首先尝试获取卡片内的footer中的标题
                        title_element = await card.query_selector('div.footer a.title span') if card else None
                        if title_element:
                            title = await title_element.text_content()
                            # logger.info(f"找到标题(方法1): {title}")
                        else:
                            # 尝试直接获取标题元素
                            title_element = await card.query_selector('a.title span') if card else None
                            if title_element:
                                title = await title_element.text_content()
                                logger.info(f"找到标题(方法2): {title}")
                            else:
                                # 尝试获取任何可能的文本内容
                                text_elements = await card.query_selector_all('span') if card else []
                                potential_titles = []
                                for text_el in text_elements:
                                    text = await text_el.text_content() if text_el else ""
                                    if text and len(text.strip()) > 5:
                                        potential_titles.append(text.strip())

                                if potential_titles:
                                    # 选择最长的文本作为标题
                                    title = max(potential_titles, key=len) if potential_titles else "未知标题"
                                    logger.info(f"找到可能的标题(方法3): {title}")
                                else:
                                    # 尝试直接获取卡片中的所有文本
                                    if not card:
                                        title = "未知标题"
                                        logger.info("卡片为空，使用默认值'未知标题'")
                                    else:
                                        all_text = await card.evaluate('el => Array.from(el.querySelectorAll("*")).map(node => node.textContent).filter(text => text && text.trim().length > 5)')
                                        if all_text and isinstance(all_text, list) and all_text:
                                            # 选择最长的文本作为标题
                                            title = max(all_text, key=len)
                                            logger.info(f"找到可能的标题(方法4): {title}")
                                        else:
                                            title = "未知标题"
                                            logger.info("无法找到标题，使用默认值'未知标题'")

                        # 如果获取到的标题为空，设为未知标题
                        if not title or (isinstance(title, str) and title.strip() == ""):
                            title = "未知标题"
                            logger.info("获取到的标题为空，使用默认值'未知标题'")
                    except Exception as e:
                        logger.info(f"获取标题时出错: {str(e)}")
                        title = "未知标题"

                    post_titles.append(title)
            except Exception as e:
                logger.info(f"处理帖子卡片时出错: {str(e)}")

        # 去重
        unique_posts = []
        seen_urls = set()
        for url, title in zip(post_links, post_titles):
            logger.info(f"title: {title}; url: {url}")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_posts.append({"url": url, "title": title})

        # 限制返回数量
        unique_posts = unique_posts[:limit]

        # logger.info(unique_posts)
        return unique_posts

    except Exception as e:
        error_message = str(e)
        logger.error(f"搜索笔记时出错: {error_message}")
        return []

@mcp.tool()
async def get_note_content(url: str) -> str:
    """获取笔记内容

    Args:
        url: 笔记 URL（可以是完整URL或小红书笔记ID）
    
    Returns:
        包含标题、作者、发布时间和内容的格式化字符串
    """
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if not browser_manager.main_page:
        return "浏览器初始化失败，请重试"

    try:
        # 使用通用URL处理函数
        processed_url = process_url(url)
        logger.info(f"处理后的URL: {processed_url}")

        # 访问帖子链接，保留完整参数
        await browser_manager.main_page.goto(processed_url, timeout=60000)
        await asyncio.sleep(10)  # 增加等待时间到10秒

        # 检查是否加载了错误页面
        if not browser_manager.main_page:
            return "浏览器初始化失败，请重试"

        error_page = await browser_manager.main_page.evaluate('''
            () => {
                // 检查常见的错误信息
                const errorTexts = [
                    "当前笔记暂时无法浏览",
                    "内容不存在",
                    "页面不存在",
                    "内容已被删除"
                ];

                for (const text of errorTexts) {
                    if (document.body.innerText.includes(text)) {
                        return {
                            isError: true,
                            errorText: text
                        };
                    }
                }

                return { isError: false };
            }
        ''')

        if error_page.get("isError", False):
            return f"无法获取笔记内容: {error_page.get('errorText', '未知错误')}\n请检查链接是否有效或尝试使用带有有效token的完整URL。"

        # 增强滚动操作以确保所有内容加载
        if not browser_manager.main_page:
            return "浏览器初始化失败，请重试"

        await browser_manager.main_page.evaluate('''
            () => {
                // 先滚动到页面底部
                window.scrollTo(0, document.body.scrollHeight);
                setTimeout(() => {
                    // 然后滚动到中间
                    window.scrollTo(0, document.body.scrollHeight / 2);
                }, 1000);
                setTimeout(() => {
                    // 最后回到顶部
                    window.scrollTo(0, 0);
                }, 2000);
            }
        ''')
        await asyncio.sleep(3)  # 等待滚动完成和内容加载

        # 获取帖子内容
        post_content = {}

        # 获取帖子标题
        try:
            title_element = await browser_manager.main_page.query_selector('#detail-title')
            if title_element:
                title = await title_element.text_content()
                post_content["标题"] = title.strip() if title else "未知标题"
            else:
                post_content["标题"] = "未知标题"
        except Exception as e:
            logger.info(f"获取标题出错: {str(e)}")
            post_content["标题"] = "未知标题"

        # 获取作者
        try:
            author_element = await browser_manager.main_page.query_selector('span.username')
            if author_element:
                author = await author_element.text_content()
                post_content["作者"] = author.strip() if author else "未知作者"
            else:
                post_content["作者"] = "未知作者"
        except Exception as e:
            logger.info(f"获取作者出错: {str(e)}")
            post_content["作者"] = "未知作者"

        # 获取发布时间
        try:
            time_element = await browser_manager.main_page.query_selector('span.date')
            if time_element:
                time_text = await time_element.text_content()
                post_content["发布时间"] = time_text.strip() if time_text else "未知"
            else:
                post_content["发布时间"] = "未知"
        except Exception as e:
            logger.info(f"获取发布时间出错: {str(e)}")
            post_content["发布时间"] = "未知"

        # 获取帖子正文内容
        try:
            content_element = await browser_manager.main_page.query_selector('#detail-desc .note-text')
            if content_element:
                content_text = await content_element.text_content()
                if content_text and len(content_text.strip()) > 50:
                    post_content["内容"] = content_text.strip()
                else:
                    post_content["内容"] = "未能获取内容"
            else:
                post_content["内容"] = "未能获取内容"
        except Exception as e:
            logger.info(f"获取正文内容出错: {str(e)}")
            post_content["内容"] = "未能获取内容"

        # 格式化返回结果
        result = f"标题: {post_content['标题']}\n"
        result += f"作者: {post_content['作者']}\n"
        result += f"发布时间: {post_content['发布时间']}\n"
        result += f"链接: {url}\n\n"
        result += f"内容:\n{post_content['内容']}"

        return result

    except Exception as e:
        return f"获取笔记内容时出错: {str(e)}"

async def main():
    """主函数 - 用于测试"""
    try:
        logger.info("正在登陆小红书 ...")
        login_result = await login()
        logger.info(f"登陆状态: {login_result}")

        url = "https://www.xiaohongshu.com/explore/683571670000000022024de3?xsec_token=AB36cgps5_rWEZ5HyjkL-9V4hR0tD163A9eqp47_nK738=&xsec_source=pc_search"
        note_content_result = await get_note_content(url)
        logger.info(f"note_content_result: {note_content_result}")

        key = "桐庐徒步"
        logger.info(f"搜索关键字: {key}")
        search_result = await search_notes(key)
        logger.info(f"search_result: {search_result}")
    except Exception as e:
        logger.error(f"执行出错: {e}")
    finally:
        # 确保资源正确关闭
        await browser_manager.close()

# FastAPI路由
@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "name": "小红书搜索MCP服务",
        "version": "1.0.0",
        "endpoints": {
            "login": "/api/login",
            "search": "/api/search",
            "note_content": "/api/note-content",
            "health": "/api/health"
        }
    }

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "xiaohongshu_scraper"}

@app.post("/api/login", response_model=LoginResponse)
async def api_login():
    """登录小红书账号"""
    try:
        result = await login()
        return LoginResponse(
            success=True,
            message=result
        )
    except Exception as e:
        logger.error(f"登录API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")

@app.post("/api/search", response_model=SearchResponse)
async def api_search(request: SearchRequest):
    """根据关键词搜索半年内评论最多的图文笔记"""
    try:
        result = await search_notes(request.keywords, request.limit)
        if isinstance(result, list):
            return SearchResponse(
                success=True,
                data=result,
                message=f"成功搜索到 {len(result)} 条结果"
            )
        else:
            return SearchResponse(
                success=False,
                data=[],
                message=str(result)
            )
    except Exception as e:
        logger.error(f"搜索API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@app.post("/api/note-content", response_model=NoteContentResponse)
async def api_get_note_content(request: NoteContentRequest):
    """获取笔记内容"""
    try:
        result = await get_note_content(request.url)
        return NoteContentResponse(
            success=True,
            data=result,
            message="成功获取笔记内容"
        )
    except Exception as e:
        logger.error(f"获取笔记内容API出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取笔记内容失败: {str(e)}")

if __name__ == "__main__":
    import os
    import multiprocessing
    import signal
    import sys
    from typing import Optional

    run_mode = os.getenv("RUN_MODE", "both")

    # 显式声明进程类型
    fastapi_process: Optional[multiprocessing.Process] = None
    mcp_process: Optional[multiprocessing.Process] = None

    def run_mcp_server_process():
        """在独立进程中运行MCP服务器"""
        logger.info("启动MCP服务器进程...")
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"MCP服务器运行出错: {e}")
    
    def run_fastapi_server_process():
        """在独立进程中运行FastAPI服务器"""
        import uvicorn
        logger.info("启动FastAPI服务器进程...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )


    def safe_terminate(proc: multiprocessing.Process, name: str):
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
                proc.close()  # 显式关闭进程资源
            except:
                pass

    def signal_handler(sig, frame):
        logger.info(f"\n收到终止信号 {sig}，开始清理进程...")
        
        # 使用具名变量确保进程引用安全
        for proc, name in [(fastapi_process, "FastAPI"), (mcp_process, "MCP")]:
            safe_terminate(proc, name)
        
        sys.exit(0)

    try:
        if run_mode in ["both", "api"]:
            fastapi_process = multiprocessing.Process(
                target=run_fastapi_server_process,
                name="FastAPI-Server",
                daemon=True  # 设置为守护进程
            )
            fastapi_process.start()
            logger.info(f"FastAPI服务器已启动 (PID: {fastapi_process.pid})")

        if run_mode in ["both", "mcp"]:
            mcp_process = multiprocessing.Process(
                target=run_mcp_server_process,
                name="MCP-Server",
                daemon=True
            )
            mcp_process.start()
            logger.info(f"MCP服务器已启动 (PID: {mcp_process.pid})")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 监控进程状态
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
