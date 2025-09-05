import json
import os
import tempfile
import base64
from typing import Tuple, Dict, List
from playwright.sync_api import sync_playwright
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlaywrightRenderer:
    """使用 Playwright 渲染 HTML 并提取占位元素布局"""
    
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
        """初始化 Playwright 浏览器实例"""
        if self._initialized:
            return
        
        try:
            self.playwright = sync_playwright().start()
            # 使用 Chromium，headless 模式
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            self.context = self.browser.new_context(
                viewport={'width': 800, 'height': 600},
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
        """清理资源"""
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
    
    def render(self, html_str: str, max_width: int = 800) -> Tuple[bytes, Dict]:
        """
        渲染 HTML 并返回背景图片和占位元素布局
        
        Args:
            html_str: HTML 字符串
            max_width: 最大宽度（像素）
            
        Returns:
            (PNG字节数据, 布局字典)
        """
        if not self._initialized:
            self.initialize()
        
        try:
            # 设置视口宽度
            self.page.set_viewport_size({'width': max_width, 'height': 600})
            
            # 加载 HTML 内容
            # 使用 data URL 避免文件操作
            data_url = f"data:text/html;charset=utf-8;base64,{base64.b64encode(html_str.encode('utf-8')).decode('ascii')}"
            self.page.goto(data_url, wait_until='networkidle')
            
            # 等待内容渲染完成
            self.page.wait_for_load_state('domcontentloaded')
            self.page.wait_for_timeout(500)  # 额外等待确保样式应用
            
            # 获取实际内容高度
            content_height = self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app) return 600;
                    const rect = app.getBoundingClientRect();
                    return Math.max(
                        rect.bottom,
                        document.documentElement.scrollHeight,
                        document.body.scrollHeight
                    );
                }
            """)
            
            # 调整视口高度以包含全部内容
            actual_height = int(content_height) + 20
            self.page.set_viewport_size({'width': max_width, 'height': actual_height})
            self.page.wait_for_timeout(100)  # 等待重新布局
            
            # 提取占位元素信息
            layout_items = self._extract_placeholder_layout()
            
            # 隐藏占位元素，准备截取背景
            self._hide_placeholders()
            
            # 截取背景图片
            png_bytes = self.page.screenshot(
                full_page=False,
                clip={'x': 0, 'y': 0, 'width': max_width, 'height': actual_height}
            )
            
            # 恢复占位元素（虽然页面会被丢弃，但保持良好习惯）
            self._show_placeholders()
            
            layout = {'items': layout_items}
            
            return png_bytes, layout
            
        except Exception as e:
            logger.error(f"Rendering failed: {e}")
            raise
    
    def _extract_placeholder_layout(self) -> List[Dict]:
        """提取所有占位元素的布局信息"""
        
        # JavaScript 代码来提取元素信息
        js_code = """
            () => {
                const items = [];
                
                // 选择所有 .placeholder 元素
                const placeholders = document.querySelectorAll('.placeholder');
                placeholders.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const item = {
                        eltid: el.getAttribute('data-eltid') || '',
                        src: el.getAttribute('data-src') || '',
                        x: Math.round(rect.left + window.scrollX),
                        y: Math.round(rect.top + window.scrollY),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    };
                    items.push(item);
                });
                
                // 选择所有带 data-src 和 data-eltid 的元素（如头像）
                const dataElements = document.querySelectorAll('[data-src][data-eltid]');
                dataElements.forEach(el => {
                    // 检查是否已经在 placeholders 中处理过
                    const eltid = el.getAttribute('data-eltid');
                    if (el.classList.contains('placeholder')) {
                        return; // 已经处理过
                    }
                    
                    const rect = el.getBoundingClientRect();
                    const item = {
                        eltid: eltid || '',
                        src: el.getAttribute('data-src') || '',
                        x: Math.round(rect.left + window.scrollX),
                        y: Math.round(rect.top + window.scrollY),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    };
                    items.push(item);
                });
                
                return items;
            }
        """
        
        items = self.page.evaluate(js_code)
        return items
    
    def _hide_placeholders(self):
        """隐藏所有占位元素，以便截取纯背景"""
        js_code = """
            () => {
                // 隐藏 .placeholder 元素
                document.querySelectorAll('.placeholder').forEach(el => {
                    el.style.visibility = 'hidden';
                });
                
                // 隐藏带 data-src 的头像等元素
                document.querySelectorAll('[data-src][data-eltid]').forEach(el => {
                    el.style.visibility = 'hidden';
                });
            }
        """
        self.page.evaluate(js_code)
    
    def _show_placeholders(self):
        """恢复显示所有占位元素"""
        js_code = """
            () => {
                // 恢复 .placeholder 元素
                document.querySelectorAll('.placeholder').forEach(el => {
                    el.style.visibility = 'visible';
                });
                
                // 恢复带 data-src 的元素
                document.querySelectorAll('[data-src][data-eltid]').forEach(el => {
                    el.style.visibility = 'visible';
                });
            }
        """
        self.page.evaluate(js_code)


# 全局渲染器实例（复用以提高性能）
_global_renderer = None

def get_renderer():
    """获取全局渲染器实例"""
    global _global_renderer
    if _global_renderer is None:
        _global_renderer = PlaywrightRenderer()
        _global_renderer.initialize()
    return _global_renderer

def cleanup_renderer():
    """清理全局渲染器"""
    global _global_renderer
    if _global_renderer:
        _global_renderer.cleanup()
        _global_renderer = None

def render_background_and_layout(html_str: str, max_width: int = 800) -> Tuple[bytes, Dict]:
    """
    调用 Playwright 渲染器：
    输入：HTML 字符串（包含占位）
    输出：背景 PNG bytes + 布局 JSON（含每个占位的 x/y/w/h/src/eltid）
    
    这个函数保持与原接口兼容
    """
    renderer = get_renderer()
    try:
        return renderer.render(html_str, max_width)
    except Exception as e:
        logger.error(f"Render failed, attempting to reinitialize: {e}")
        # 如果失败，尝试重新初始化
        cleanup_renderer()
        renderer = get_renderer()
        return renderer.render(html_str, max_width)

# 注册清理函数
import atexit
atexit.register(cleanup_renderer)