import io
import base64
from flask import Flask, render_template, request, send_file, jsonify
from utils import Config
from renderer import render_background_and_layout
from composer import compose_png, compose_apng

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

@app.after_request
def set_headers(response):
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    return 'see https://github.com/zhullyb/qq-quote-generator/blob/main/README.md'

def _load_request_json():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        # 按要求：不做严格安全校验，仅做最轻类型检查
        raise ValueError("Request body must be a JSON array of messages")
    return data

@app.route('/png/', methods=['POST'])
def png_handler():
    try:
        data_list = _load_request_json()
        bg_png_bytes, layout = render_background_and_layout(
            render_template('main-template.html', data_list=data_list)
        )
        png_bytes = compose_png(bg_png_bytes, layout)
        return send_file(io.BytesIO(png_bytes), mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/base64/', methods=['POST'])
def base64_handler():
    try:
        data_list = _load_request_json()
        bg_png_bytes, layout = render_background_and_layout(
            render_template('main-template.html', data_list=data_list)
        )
        png_bytes = compose_png(bg_png_bytes, layout)
        return base64.b64encode(png_bytes).decode('ascii')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/apng/', methods=['POST'])
def apng_handler():
    try:
        data_list = _load_request_json()
        bg_png_bytes, layout = render_background_and_layout(
            render_template('main-template.html', data_list=data_list)
        )
        apng_bytes = compose_apng(bg_png_bytes, layout)
        return send_file(io.BytesIO(apng_bytes), mimetype='image/apng')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/quote/', methods=['GET', 'POST'])
def quote_preview():
    if request.method == 'POST':
        data_list = _load_request_json()
    else:
        data_list = []
    return render_template('main-template.html', data_list=data_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT, debug=Config.FLASK_DEBUG)