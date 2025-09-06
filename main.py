import io
import base64
from flask import Flask, render_template, request, send_file, jsonify
from utils import Config

# 1. Import the new initialization function
from renderer import render_background_and_layout, initialize_playwright_pool
from composer import compose_png, compose_apng, compose_webp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# 2. Initialize the pool right after creating the Flask app instance
# This ensures it's ready before the server starts accepting requests.
initialize_playwright_pool()

@app.after_request
def set_headers(response):
    # ... (rest of the file is identical)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    return 'see https://github.com/zhullyb/qq-quote-generator/blob/main/README.md'

def _load_request_json():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
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

# ... (all other routes are identical) ...

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

@app.route('/webp/', methods=['POST'])
def webp_handler():
    try:
        data_list = _load_request_json()
        bg_png_bytes, layout = render_background_and_layout(
            render_template('main-template.html', data_list=data_list)
        )
        webp_bytes = compose_webp(bg_png_bytes, layout)
        return send_file(io.BytesIO(webp_bytes), mimetype='image/webp')
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
    # The initialization is now done above, before the server loop starts
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT, debug=Config.FLASK_DEBUG)
