import io
from uuid import uuid4
from flask import Flask, render_template, request, send_file

from utils import Config
from screenshot import Screenshot
from anim import prepare_animated_asset, compose_animation_event_driven

app = Flask(__name__)

data_dict = {}
ss = Screenshot()  # 复用内部的 ScreenshotPool


@app.after_request
def set_headers(response):
    response.headers["Referrer-Policy"] = 'no-referrer'
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    return 'see https://github.com/zhullyb/qq-quote-generator/blob/main/README.md'


def _prepare_placeholders_and_assets(data_list):
    """
    遍历消息，下载并识别动图：
    - 静态图：保持字符串 URL
    - 动图(帧数>1)：替换为占位 dict {"id", "width", "height"}，并收集 AnimatedAsset
    """
    assets = {}
    for block in data_list:
        if "image" not in block:
            continue
        new_images = []
        for img in block["image"]:
            if not isinstance(img, str):
                new_images.append(img)
                continue
            try:
                pid = f"anim-{uuid4().hex[:8]}"
                asset = prepare_animated_asset(img, pid, border_radius_px=Config.IMAGE_BORDER_RADIUS_PX)
                if len(asset.frames_rgba) <= 1:
                    new_images.append(img)  # 静态
                else:
                    w, h = asset.display_size
                    new_images.append({"id": pid, "width": w, "height": h})
                    assets[pid] = asset
            except Exception:
                # 下载/解析失败则退回静态
                new_images.append(img)
        block["image"] = new_images
    return assets


def _render_and_maybe_compose(ret_format: str):
    unique_id = str(uuid4())
    payload = request.get_json(force=True, silent=False) or []
    # 保存原始数据供模板渲染
    data_dict[unique_id] = payload

    # 用于替换占位与收集资产
    assets_map = _prepare_placeholders_and_assets(data_dict[unique_id])

    try:
        # 静态路径：原样返回
        if ret_format in ('png', 'base64'):
            out = ss.screenshot(ret_format, unique_id)
            if ret_format == 'png':
                return send_file(io.BytesIO(out), mimetype='image/png')
            return out

        # 动图路径：先拿到底图 + 占位坐标
        base_png, boxes_map = ss.pool.render_with_boxes(unique_id)
        fmt = 'APNG' if ret_format == 'apng' else 'GIF'
        composed = compose_animation_event_driven(base_png, boxes_map, list(assets_map.values()), fmt=fmt)
        if ret_format == 'apng':
            return send_file(io.BytesIO(composed), mimetype='image/apng')
        else:
            return send_file(io.BytesIO(composed), mimetype='image/gif')

    finally:
        data_dict.pop(unique_id, None)


@app.route('/base64/', methods=['POST'])
def base64_handler_trigger():
    return _render_and_maybe_compose('base64')


@app.route('/png/', methods=['POST'])
def png_handler_trigger():
    return _render_and_maybe_compose('png')


@app.route('/apng/', methods=['POST'])
def apng_handler_trigger():
    return _render_and_maybe_compose('apng')


@app.route('/gif/', methods=['POST'])
def gif_handler_trigger():
    return _render_and_maybe_compose('gif')


@app.route('/quote/', methods=['GET', 'POST'])
def quote():
    unique_id = request.args.get('id')
    data = data_dict.get(unique_id, [])
    return render_template('main-template.html', data_list=data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)