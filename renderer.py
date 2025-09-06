import atexit
import base64
import logging
import threading  # 1. 导入 threading
from typing import Dict, List, Tuple

from playwright.sync_api import sync_playwright
from utils import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. 创建一个线程本地存储对象，替代全局变量 _global_renderer
_thread_local = threading.local()


class PlaywrightRenderer:
    """使用 Playwright 渲染 HTML 并提取占位元素布局（支持圆角/圆形与适配模式）"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def initialize(self):
        if self._initialized:
            return
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=Config.PLAYWRIGHT_HEADLESS,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            self.context = self.browser.new_context(
                viewport={'width': Config.DEFAULT_VIEWPORT_WIDTH, 'height': 600},
                device_scale_factor=1,
                ignore_https_errors=True
            )
            self.page = self.context.new_page()
            self._initialized = True
            logger.info(f"Playwright renderer initialized for thread {threading.get_ident()}")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    def cleanup(self):
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()
        self._initialized = False
        logger.info(f"Playwright renderer cleaned up for thread {threading.get_ident()}")

    def render(self, html_str: str, max_width: int = None) -> Tuple[bytes, Dict]:
        if not self._initialized:
            self.initialize()

        try:
            width = max_width or Config.DEFAULT_VIEWPORT_WIDTH
            width = max(320, min(width, Config.MAX_VIEWPORT_WIDTH))

            self.page.set_viewport_size({'width': width, 'height': 600})
            self.page.set_content(html_str, wait_until='domcontentloaded')

            content_height = self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app) return 600;
                    return Math.max(app.getBoundingClientRect().bottom, document.documentElement.scrollHeight);
                }
            """)
            actual_height = int(content_height) + 20
            actual_height = max(Config.MIN_VIEWPORT_HEIGHT, min(actual_height, Config.MAX_VIEWPORT_HEIGHT))

            self.page.set_viewport_size({'width': width, 'height': actual_height})
            layout_items = self._extract_placeholder_layout()
            self._hide_placeholders()

            png_bytes = self.page.screenshot(
                full_page=False,
                clip={'x': 0, 'y': 0, 'width': width, 'height': actual_height}
            )
            self._show_placeholders()

            return png_bytes, {'items': layout_items}
        except Exception as e:
            logger.error(f"Rendering failed: {e}")
            raise

    def _extract_placeholder_layout(self) -> List[Dict]:
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
        return self.page.evaluate(js_code)

    def _hide_placeholders(self):
        self.page.evaluate("() => { document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => el.style.visibility = 'hidden'); }")

    def _show_placeholders(self):
        self.page.evaluate("() => { document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => el.style.visibility = 'visible'); }")


def get_renderer():
    """3. 获取当前线程的渲染器实例，如果不存在则创建并初始化"""
    renderer = getattr(_thread_local, 'renderer', None)
    if renderer is None:
        renderer = PlaywrightRenderer()
        renderer.initialize()
        _thread_local.renderer = renderer
    return renderer


def cleanup_renderer():
    """4. 清理当前线程的渲染器"""
    renderer = getattr(_thread_local, 'renderer', None)
    if renderer:
        renderer.cleanup()
        delattr(_thread_local, 'renderer')


def render_background_and_layout(html_str: str, max_width: int = None) -> Tuple[bytes, Dict]:
    renderer = get_renderer()
    try:
        return renderer.render(html_str, max_width)
    except Exception as e:
        logger.error(f"Render failed, attempting to reinitialize for thread {threading.get_ident()}: {e}")
        # 重新初始化当前线程的渲染器
        cleanup_renderer()
        renderer = get_renderer()
        return renderer.render(html_str, max_width)


# atexit 会在主线程退出时调用，用于清理主线程可能创建的实例
atexit.register(cleanup_renderer)