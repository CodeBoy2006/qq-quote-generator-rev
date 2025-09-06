import base64
import logging
from typing import Tuple, Dict, List

from playwright.sync_api import sync_playwright
from utils import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            logger.info("Playwright renderer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    def cleanup(self):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self._initialized = False
        logger.info("Playwright renderer cleaned up")

    def render(self, html_str: str, max_width: int = None) -> Tuple[bytes, Dict]:
        if not self._initialized:
            self.initialize()

        try:
            width = max_width or Config.DEFAULT_VIEWPORT_WIDTH
            width = max(320, min(width, Config.MAX_VIEWPORT_WIDTH))

            self.page.set_viewport_size({'width': width, 'height': 600})

            # 直接注入 HTML，比 data:URL 更快；模板无外链资源，等待 DOMContentLoaded 即可
            self.page.set_content(html_str, wait_until='domcontentloaded')

            content_height = self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app) return 600;
                    const rect = app.getBoundingClientRect();
                    return Math.max(rect.bottom, document.documentElement.scrollHeight, document.body.scrollHeight);
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
                    // 仅取第一个半径（统一圆角）
                    const token = str.split('/')[0].trim().split(/\s+/)[0];
                    if (token.endsWith('%')) {
                        const p = parseFloat(token);
                        if (isNaN(p)) return 0;
                        const r = Math.round(Math.min(w, h) * p / 100);
                        return r;
                    } else if (token.endsWith('px')) {
                        const v = parseFloat(token);
                        return isNaN(v) ? 0 : Math.round(v);
                    } else {
                        const v = parseFloat(token);
                        return isNaN(v) ? 0 : Math.round(v);
                    }
                }

                function fitMode(el) {
                    // 头像尽量 cover 填满（配合圆形 mask），其它图片使用 contain
                    if (el.classList.contains('avatar')) return 'cover';
                    return 'contain';
                }

                function shapeOf(el, w, h, radiusPx, style) {
                    // class 指定为 avatar 或 50% 且近似正方形 → circle
                    if (el.classList.contains('avatar')) return 'circle';
                    const br = style.borderRadius || '';
                    const isPct50 = /(^|\s)50%(\s|$)/.test(br);
                    const squareish = Math.abs(w - h) <= 2;
                    if (isPct50 && squareish) return 'circle';
                    return 'rect';
                }

                const nodes = document.querySelectorAll('.placeholder, [data-src][data-eltid]');
                nodes.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const w = Math.round(rect.width), h = Math.round(rect.height);
                    const x = Math.round(rect.left + window.scrollX);
                    const y = Math.round(rect.top + window.scrollY);

                    const eltid = el.getAttribute('data-eltid') || '';
                    const src = el.getAttribute('data-src') || '';
                    const radiusPx = radiusToPx(style.borderRadius, w, h);
                    const shape = shapeOf(el, w, h, radiusPx, style);
                    const fit = fitMode(el);

                    items.push({
                        eltid, src, x, y, w, h,
                        radius: radiusPx,
                        shape,         // 'circle' | 'rect'
                        fit            // 'contain' | 'cover'
                    });
                });
                return items;
            }
        """
        return self.page.evaluate(js_code)

    def _hide_placeholders(self):
        js_code = """
            () => {
                document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => {
                    el.style.visibility = 'hidden';
                });
            }
        """
        self.page.evaluate(js_code)

    def _show_placeholders(self):
        js_code = """
            () => {
                document.querySelectorAll('.placeholder, [data-src][data-eltid]').forEach(el => {
                    el.style.visibility = 'visible';
                });
            }
        """
        self.page.evaluate(js_code)


_global_renderer = None

def get_renderer():
    global _global_renderer
    if _global_renderer is None:
        _global_renderer = PlaywrightRenderer()
        _global_renderer.initialize()
    return _global_renderer

def cleanup_renderer():
    global _global_renderer
    if _global_renderer:
        _global_renderer.cleanup()
        _global_renderer = None

def render_background_and_layout(html_str: str, max_width: int = None) -> Tuple[bytes, Dict]:
    renderer = get_renderer()
    try:
        return renderer.render(html_str, max_width)
    except Exception as e:
        logger.error(f"Render failed, attempting to reinitialize: {e}")
        cleanup_renderer()
        renderer = get_renderer()
        return renderer.render(html_str, max_width)

import atexit
atexit.register(cleanup_renderer)