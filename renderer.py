import atexit
import logging
import queue
from contextlib import contextmanager
from typing import Dict, List, Tuple

from playwright.sync_api import sync_playwright, Browser, Page
from utils import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlaywrightPool:
    """
    管理一个单一的、持久化的 Playwright 浏览器实例
    以及一个可供多线程安全借用和归还的页面（Page）池。
    """
    def __init__(self, pool_size: int):
        self.pool_size = pool_size
        self.playwright = None
        self.browser: Browser = None
        self.page_pool: queue.Queue = None
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=Config.PLAYWRIGHT_HEADLESS,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            self.page_pool = queue.Queue(maxsize=self.pool_size)
            for _ in range(self.pool_size):
                # 每个页面使用独立的 context，提供更好的隔离性
                context = self.browser.new_context(
                    viewport={'width': Config.DEFAULT_VIEWPORT_WIDTH, 'height': 600},
                    device_scale_factor=1,
                    ignore_https_errors=True
                )
                page = context.new_page()
                self.page_pool.put(page)
            self._initialized = True
            logger.info(f"Playwright pool initialized with {self.pool_size} pages.")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright pool: {e}")
            self.cleanup()  # 初始化失败时尝试清理
            raise

    def cleanup(self):
        if not self._initialized:
            return
        # 清理池中的所有页面及其上下文
        while not self.page_pool.empty():
            try:
                page = self.page_pool.get_nowait()
                context = page.context
                page.close()
                context.close()
            except queue.Empty:
                break
            except Exception as e:
                logger.warning(f"Error closing a page/context during cleanup: {e}")
        
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self._initialized = False
        logger.info("Playwright pool cleaned up.")

    @contextmanager
    def get_page(self, timeout=30) -> Page:
        """
        从池中获取一个页面，使用完毕后自动归还。
        这是一个上下文管理器，推荐使用 'with' 语句。
        """
        if not self._initialized:
            self.initialize()
            
        page = None
        try:
            page = self.page_pool.get(timeout=timeout)
            yield page
        finally:
            if page:
                self.page_pool.put(page)


# 创建全局唯一的 Playwright 池实例
_pool = PlaywrightPool(pool_size=Config.PLAYWRIGHT_POOL_SIZE)

# 注册清理函数，确保程序退出时浏览器被关闭
atexit.register(_pool.cleanup)


def render_background_and_layout(html_str: str, max_width: int = None) -> Tuple[bytes, Dict]:
    """
    使用页面池中的一个页面来渲染 HTML。
    此函数现在是完全线程安全的。
    """
    try:
        with _pool.get_page() as page:
            width = max_width or Config.DEFAULT_VIEWPORT_WIDTH
            width = max(320, min(width, Config.MAX_VIEWPORT_WIDTH))

            page.set_viewport_size({'width': width, 'height': 600})
            page.set_content(html_str, wait_until='domcontentloaded')

            content_height = page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app) return 600;
                    return Math.max(app.getBoundingClientRect().bottom, document.documentElement.scrollHeight);
                }
            """)
            actual_height = int(content_height) + 20
            actual_height = max(Config.MIN_VIEWPORT_HEIGHT, min(actual_height, Config.MAX_VIEWPORT_HEIGHT))
            
            page.set_viewport_size({'width': width, 'height': actual_height})
            
            layout_items = _extract_placeholder_layout(page)
            _hide_placeholders(page)

            png_bytes = page.screenshot(
                full_page=False,
                clip={'x': 0, 'y': 0, 'width': width, 'height': actual_height}
            )
            _show_placeholders(page)

            return png_bytes, {'items': layout_items}

    except queue.Empty:
        logger.error("Failed to get a page from the pool: Timeout reached. The service is likely overloaded.")
        raise TimeoutError("Renderer service is busy, please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during rendering: {e}")
        raise


def _extract_placeholder_layout(page: Page) -> List[Dict]:
    js_code = r"""
        () => {
            const items = [];
            function radiusToPx(str, w, h) {
                if (!str) return 0;
                str = String(str).trim();
                const token = str.split('/')[0].trim().split(/\s+/)[0];
                if (token.endsWith('%')) {
                    const p = parseFloat(token);
                    return isNaN(p) ? 0 : Math.round(Math.min(w, h) * p / 100);
                } else if (token.endsWith('px')) {
                    const v = parseFloat(token);
                    return isNaN(v) ? 0 : Math.round(v);
                }
                const v = parseFloat(token);
                return isNaN(v) ? 0 : Math.round(v);
            }
            function fitMode(el) { return el.classList.contains('avatar') ? 'cover' : 'contain'; }
            function shapeOf(el, w, h, style) {
                if (el.classList.contains('avatar')) return 'circle';
                const br = style.borderRadius || '';
                const isPct50 = /(^|\s)50%(\s|$)/.test(br);
                if (isPct50 && Math.abs(w - h) <= 2) return 'circle';
                return 'rect';
            }
            document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const w = Math.round(rect.width), h = Math.round(rect.height);
                items.push({
                    eltid: el.getAttribute('data-eltid') || '',
                    src: el.getAttribute('data-src') || '',
                    x: Math.round(rect.left + window.scrollX),
                    y: Math.round(rect.top + window.scrollY), w, h,
                    radius: radiusToPx(style.borderRadius, w, h),
                    shape: shapeOf(el, w, h, style),
                    fit: fitMode(el)
                });
            });
            return items;
        }
    """
    return page.evaluate(js_code)


def _hide_placeholders(page: Page):
    page.evaluate("() => { document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => el.style.visibility = 'hidden'); }")


def _show_placeholders(page: Page):
    page.evaluate("() => { document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => el.style.visibility = 'visible'); }")
