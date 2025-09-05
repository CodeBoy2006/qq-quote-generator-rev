import json
import os
import subprocess
import tempfile
from typing import Tuple, Dict

RENDER_BIN = os.environ.get("LITEHTML_RENDER_BIN", os.path.join(os.path.dirname(__file__), "native", "build", "litehtml_renderer"))

def render_background_and_layout(html_str: str, max_width: int = 800) -> Tuple[bytes, Dict]:
    """调用本地 C++ 渲染器：
       输入：HTML 字符串（包含占位）
       输出：背景 PNG bytes + 布局 JSON（含每个占位的 x/y/w/h/src/eltid）
    """
    if not os.path.isfile(RENDER_BIN):
        raise RuntimeError(f"litehtml renderer not found at {RENDER_BIN}. Build native first.")

    with tempfile.TemporaryDirectory() as td:
        in_html = os.path.join(td, "in.html")
        out_png = os.path.join(td, "bg.png")
        out_json = os.path.join(td, "layout.json")

        with open(in_html, "w", encoding="utf-8") as f:
            f.write(html_str)

        cmd = [
            RENDER_BIN,
            "-i", in_html,
            "-o", out_png,
            "-l", out_json,
            "-w", str(max_width)
        ]
        subprocess.run(cmd, check=True)

        with open(out_png, "rb") as f:
            png_bytes = f.read()
        with open(out_json, "r", encoding="utf-8") as f:
            layout = json.load(f)

        return png_bytes, layout