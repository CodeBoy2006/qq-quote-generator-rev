import os

class Config(object):
    FLASK_RUN_PORT = int(os.environ.get('FLASK_RUN_PORT') or 5000)
    GECKODRIVER_PATH = os.environ.get('GECKODRIVER_PATH') or None

    # 并发（浏览器 worker 池）
    WORKER_POOL_SIZE = int(os.environ.get('WORKER_POOL_SIZE') or 2)
    WORKER_ACQUIRE_TIMEOUT_SEC = int(os.environ.get('WORKER_ACQUIRE_TIMEOUT_SEC') or 30)

    # 样式同步（与 CSS .image/.single-image 一致）
    IMAGE_BORDER_RADIUS_PX = int(os.environ.get('IMAGE_BORDER_RADIUS_PX') or 15)
    MAX_IMAGE_RENDER_W = int(os.environ.get('MAX_IMAGE_RENDER_W') or 500)
    MAX_IMAGE_RENDER_H = int(os.environ.get('MAX_IMAGE_RENDER_H') or 500)

    # 事件时间线护栏（避免极端 LCM 爆炸）
    TIMELINE_MAX_EVENTS = int(os.environ.get('TIMELINE_MAX_EVENTS') or 5000)
    TIMELINE_MAX_SECONDS = float(os.environ.get('TIMELINE_MAX_SECONDS') or 60.0)

    # APNG 精度（分母上限 + 容许误差）
    APNG_MAX_DEN = int(os.environ.get('APNG_MAX_DEN') or 1000)      # 单帧 delay 分母上限
    APNG_DELAY_TOL_MS = float(os.environ.get('APNG_DELAY_TOL_MS') or 0.5)  # 单帧时长容忍误差（毫秒）

    # GIF 量化（时间与色彩）
    GIF_MIN_DELAY_MS = int(os.environ.get('GIF_MIN_DELAY_MS') or 20)  # 常见浏览器对 <20ms 会夹紧
    GIF_ROUND_TO_MS = int(os.environ.get('GIF_ROUND_TO_MS') or 10)    # GIF 1/100s 精度，10ms 对齐
    GIF_COLORS = int(os.environ.get('GIF_COLORS') or 256)

    # 外部优化工具（可选，无则忽略）
    USE_GIFSICLE = (os.environ.get('USE_GIFSICLE', '1') == '1')  # 若容器内已安装则自动使用