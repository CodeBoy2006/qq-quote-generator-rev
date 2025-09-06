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

    # ====== 性能/缓存可配项 ======
    # 下载缓存（内存 LRU + TTL）
    CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', 300))   # 缓存 5 分钟
    CACHE_MAX_ENTRIES = int(os.environ.get('CACHE_MAX_ENTRIES', 256))

    # 动画总时长上限（毫秒），避免超长动图生成巨量帧；仍“尽量无损”地抽关键变更点
    MAX_ANIM_TOTAL_MS = int(os.environ.get('MAX_ANIM_TOTAL_MS', 10000))  # 10s 上限
    DEFAULT_STATIC_FRAME_MS = int(os.environ.get('DEFAULT_STATIC_FRAME_MS', 1000))

    # 重采样算法：LANCZOS 画质更好但稍慢；BILINEAR 更快
    RESAMPLE = os.environ.get('RESAMPLE', 'LANCZOS').upper()  # 'LANCZOS' 或 'BILINEAR'