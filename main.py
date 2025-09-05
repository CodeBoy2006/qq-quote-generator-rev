import io
import base64
from flask import Flask, render_template, request, send_file
from uuid import uuid4
from utils import Config
from renderer import render_background_and_layout
from composer import compose_png, compose_apng

app = Flask(__name__)

@app.after_request
def set_headers(response):
    response.headers["Referrer-Policy"] = 'no-referrer'
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    return 'see https://github.com/zhullyb/qq-quote-generator/blob/main/README.md'

def _load_request_json():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        # 按你的要求，这里不做严格安全校验，仅做最轻的类型检查
        raise ValueError("Request body must be a JSON array of messages")
    return data

@app.route('/png/', methods=['POST'])
def png_handler():
    """原有接口：返回 image/png；用“占位渲染 + 贴回静态帧”实现"""
    data_list = _load_request_json()
    # 1) 用 Jinja2 产出 HTML（包含占位） -> 2) 调用 litehtml 渲染器返回 背景PNG + 占位布局
    bg_png_bytes, layout = render_background_and_layout(render_template('main-template.html', data_list=data_list))

    # 3) 叠加静态帧（动图取首帧） -> PNG
    png_bytes = compose_png(bg_png_bytes, layout)
    return send_file(io.BytesIO(png_bytes), mimetype='image/png')

@app.route('/base64/', methods=['POST'])
def base64_handler():
    """原有接口：返回 base64（PNG 的 Base64），保持一致"""
    data_list = _load_request_json()
    bg_png_bytes, layout = render_background_and_layout(render_template('main-template.html', data_list=data_list))
    png_bytes = compose_png(bg_png_bytes, layout)
    return base64.b64encode(png_bytes).decode('ascii')

@app.route('/apng/', methods=['POST'])
def apng_handler():
    """新增：返回 image/apng（静态背景 + 多动图合成）"""
    data_list = _load_request_json()
    bg_png_bytes, layout = render_background_and_layout(render_template('main-template.html', data_list=data_list))
    apng_bytes = compose_apng(bg_png_bytes, layout)
    return send_file(io.BytesIO(apng_bytes), mimetype='image/apng')

@app.route('/quote/', methods=['GET', 'POST'])
def quote_preview():
    """保留：预览 HTML（调试用）"""
    # 为兼容原行为，GET 可不带数据；POST 时显示传入
    if request.method == 'POST':
        data_list = _load_request_json()
    else:
        data_list = []
    return render_template('main-template.html', data_list=data_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)