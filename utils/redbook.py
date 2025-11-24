from typing import List, Dict
import sys
import asyncio
from urllib.parse import quote
from loguru import logger
from playwright.async_api import async_playwright


logger.remove()
logger.level("DEBUG")
logger.add(
    sys.stdout,
    colorize=True,
    format="<g>{time:YYYY-MM-DD HH:mm:ss}</g> | {level} | {message}",
)


class BrowserManager:
    """封装 Playwright 浏览器生命周期管理"""

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
                    playwright_instance = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
                    self.browser_context = playwright_instance.contexts[0]
                    logger.info("打开一个新标签页 ...")

                    valid_pages = [p for p in self.browser_context.pages if not p.is_closed()]
                    if valid_pages:
                        self.main_page = valid_pages[0]
                        for page in self.browser_context.pages[1:]:
                            if not page.is_closed():
                                await page.close()
                    else:
                        self.main_page = await self.browser_context.new_page()

                    self.main_page.set_default_timeout(60000)
                except Exception as e:
                    logger.error(f"浏览器初始化失败: {str(e)}")
                    raise

            if not self.main_page or self.main_page.is_closed():
                self.main_page = await self.browser_context.new_page()

            if not self.is_logged_in:
                try:
                    await self.main_page.goto("https://www.xiaohongshu.com", timeout=60000)
                    await asyncio.sleep(3)

                    login_selector = [
                        'text="登录"',
                        'button:has-text("登录")',
                        'a:has-text("登录")',
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


browser_manager = BrowserManager()

def process_url(url: str) -> str:
    """处理URL，确保格式正确并保留所有参数"""
    processed_url = url.strip()

    if processed_url.startswith("@"):
        processed_url = processed_url[1:]

    if processed_url.startswith("http://"):
        processed_url = "https://" + processed_url[7:]
    elif not processed_url.startswith("https://"):
        processed_url = "https://" + processed_url

    if "xiaohongshu.com" in processed_url and "www.xiaohongshu.com" not in processed_url:
        processed_url = processed_url.replace("xiaohongshu.com", "www.xiaohongshu.com")

    return processed_url


async def login_action() -> str:
    """登录小红书账号"""
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if browser_manager.is_logged_in:
        return "已登录小红书账号"

    if not browser_manager.main_page:
        return "浏览器初始化失败，请重试"

    await browser_manager.main_page.goto("https://www.xiaohongshu.com", timeout=60000)
    await asyncio.sleep(3)

    login_elements = await browser_manager.main_page.query_selector_all('text="登录"')
    if login_elements:
        await login_elements[0].click()
        max_wait_time = 180
        wait_interval = 5
        waited_time = 0

        while waited_time < max_wait_time:
            if not browser_manager.main_page:
                return "浏览器初始化失败，请重试"

            still_login = await browser_manager.main_page.query_selector_all('text="登录"')
            if not still_login:
                browser_manager.is_logged_in = True
                await asyncio.sleep(2)
                return "登录成功！"

            await asyncio.sleep(wait_interval)
            waited_time += wait_interval

        return "登录等待超时。请重试或手动登录后再使用其他功能。"
    else:
        browser_manager.is_logged_in = True
        return "已登录小红书账号"


async def search_notes(keywords: str, limit: int = 30) -> List[Dict[str, str]]:
    """根据关键词搜索半年内评论最多的图文笔记"""
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        logger.error("请先登录小红书账号")
        return []

    if not browser_manager.main_page:
        logger.error("浏览器初始化失败，请重试")
        return []

    encoded_keywords = quote(keywords)
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keywords}"
    try:
        await browser_manager.main_page.goto(search_url, timeout=60000)
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

        page_html = await browser_manager.main_page.content()
        logger.info(f"页面HTML片段: {page_html[10000:10500]}...")
        logger.info("尝试获取帖子卡片...")

        post_cards = await browser_manager.main_page.query_selector_all("section.note-item")
        logger.info(f"找到 {len(post_cards)} 个帖子卡片")

        if not post_cards:
            post_cards = await browser_manager.main_page.query_selector_all("div[data-v-a264b01a]")
            logger.info(f"使用备用选择器找到 {len(post_cards)} 个帖子卡片")

        post_links = []
        post_titles = []

        for card in post_cards:
            try:
                link_element = await card.query_selector('a[href*="/search_result/"]') if card else None
                if not link_element:
                    continue

                href = await link_element.get_attribute("href")
                if href and "/search_result/" in href:
                    if href.startswith("/"):
                        full_url = f"https://www.xiaohongshu.com{href}"
                    else:
                        full_url = href

                    post_links.append(full_url)

                    try:
                        title_element = await card.query_selector("div.footer a.title span") if card else None
                        if title_element:
                            title = await title_element.text_content()
                        else:
                            title_element = await card.query_selector("a.title span") if card else None
                            if title_element:
                                title = await title_element.text_content()
                            else:
                                text_elements = await card.query_selector_all("span") if card else []
                                potential_titles = []
                                for text_el in text_elements:
                                    text = await text_el.text_content() if text_el else ""
                                    if text and len(text.strip()) > 5:
                                        potential_titles.append(text.strip())

                                if potential_titles:
                                    title = max(potential_titles, key=len)
                                else:
                                    if not card:
                                        title = "未知标题"
                                    else:
                                        all_text = await card.evaluate(
                                            "el => Array.from(el.querySelectorAll('*')).map(node => node.textContent).filter(text => text && text.trim().length > 5)"
                                        )
                                        if all_text and isinstance(all_text, list) and all_text:
                                            title = max(all_text, key=len)
                                        else:
                                            title = "未知标题"

                        if not title or (isinstance(title, str) and title.strip() == ""):
                            title = "未知标题"
                    except Exception as e:
                        logger.info(f"获取标题时出错: {str(e)}")
                        title = "未知标题"

                    post_titles.append(title)
            except Exception as e:
                logger.info(f"处理帖子卡片时出错: {str(e)}")

        unique_posts = []
        seen_urls = set()
        for url, title in zip(post_links, post_titles):
            logger.info(f"title: {title}; url: {url}")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_posts.append({"url": url, "title": title})

        unique_posts = unique_posts[:limit]
        return unique_posts

    except Exception as e:
        error_message = str(e)
        logger.error(f"搜索笔记时出错: {error_message}")
        return []


async def get_note_content(url: str) -> str:
    """获取笔记内容"""
    login_status = await browser_manager.ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if not browser_manager.main_page:
        return "浏览器初始化失败，请重试"

    try:
        processed_url = process_url(url)
        logger.info(f"处理后的URL: {processed_url}")

        await browser_manager.main_page.goto(processed_url, timeout=60000)
        await asyncio.sleep(10)

        if not browser_manager.main_page:
            return "浏览器初始化失败，请重试"

        error_page = await browser_manager.main_page.evaluate(
            """
            () => {
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
        """
        )

        if error_page.get("isError", False):
            return f"无法获取笔记内容: {error_page.get('errorText', '未知错误')}\n请检查链接是否有效或尝试使用带有有效token的完整URL。"

        if not browser_manager.main_page:
            return "浏览器初始化失败，请重试"

        await browser_manager.main_page.evaluate(
            """
            () => {
                window.scrollTo(0, document.body.scrollHeight);
                setTimeout(() => {
                    window.scrollTo(0, document.body.scrollHeight / 2);
                }, 1000);
                setTimeout(() => {
                    window.scrollTo(0, 0);
                }, 2000);
            }
        """
        )
        await asyncio.sleep(3)

        post_content: Dict[str, str] = {}

        try:
            title_element = await browser_manager.main_page.query_selector("#detail-title")
            if title_element:
                title = await title_element.text_content()
                post_content["标题"] = title.strip() if title else "未知标题"
            else:
                post_content["标题"] = "未知标题"
        except Exception as e:
            logger.info(f"获取标题出错: {str(e)}")
            post_content["标题"] = "未知标题"

        try:
            author_element = await browser_manager.main_page.query_selector("span.username")
            if author_element:
                author = await author_element.text_content()
                post_content["作者"] = author.strip() if author else "未知作者"
            else:
                post_content["作者"] = "未知作者"
        except Exception as e:
            logger.info(f"获取作者出错: {str(e)}")
            post_content["作者"] = "未知作者"

        try:
            time_element = await browser_manager.main_page.query_selector("span.date")
            if time_element:
                time_text = await time_element.text_content()
                post_content["发布时间"] = time_text.strip() if time_text else "未知"
            else:
                post_content["发布时间"] = "未知"
        except Exception as e:
            logger.info(f"获取发布时间出错: {str(e)}")
            post_content["发布时间"] = "未知"

        try:
            content_element = await browser_manager.main_page.query_selector("#detail-desc .note-text")
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

        result = f"标题: {post_content['标题']}\n"
        result += f"作者: {post_content['作者']}\n"
        result += f"发布时间: {post_content['发布时间']}\n"
        result += f"链接: {url}\n\n"
        result += f"内容:\n{post_content['内容']}"

        return result

    except Exception as e:
        return f"获取笔记内容时出错: {str(e)}"


async def shutdown_browser():
    """关闭浏览器资源供外部调用"""
    await browser_manager.close()
