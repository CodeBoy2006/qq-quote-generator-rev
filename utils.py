import os

class Config:
    """应用配置"""
    FLASK_RUN_PORT = int(os.environ.get('FLASK_RUN_PORT', 5000))
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size
    
    # Playwright 配置
    PLAYWRIGHT_HEADLESS = os.environ.get('PLAYWRIGHT_HEADLESS', 'True').lower() == 'true'
    PLAYWRIGHT_TIMEOUT = int(os.environ.get('PLAYWRIGHT_TIMEOUT', 30000))  # 毫秒
    
    # 渲染配置
    DEFAULT_VIEWPORT_WIDTH = 800
    MAX_VIEWPORT_WIDTH = 1920
    MIN_VIEWPORT_HEIGHT = 100
    MAX_VIEWPORT_HEIGHT = 10000