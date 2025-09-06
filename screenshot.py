from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import Config

import threading
import time


class _BrowserWorker:
    def __init__(self, geckodriver_path=None):
        opts = Options()
        opts.add_argument("--headless")
        service = Service(executable_path=geckodriver_path) if geckodriver_path else None
        self.driver = webdriver.Firefox(options=opts, service=service) if service else webdriver.Firefox(options=opts)
        self.lock = threading.Lock()

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass


class ScreenshotPool:
    def __init__(self, size: int):
        self._workers = [_BrowserWorker(Config.GECKODRIVER_PATH) for _ in range(size)]
        self._cv = threading.Condition()
        self._busy = set()

    def acquire(self, timeout=Config.WORKER_ACQUIRE_TIMEOUT_SEC):
        with self._cv:
            end = time.time() + timeout
            while True:
                for i, w in enumerate(self._workers):
                    if i not in self._busy:
                        self._busy.add(i)
                        return i, w
                remain = end - time.time()
                if remain <= 0:
                    raise TimeoutError("No free browser worker")
                self._cv.wait(timeout=remain)

    def release(self, idx: int):
        with self._cv:
            self._busy.discard(idx)
            self._cv.notify()

    def shutdown(self):
        for w in self._workers:
            w.close()

    def render_with_boxes(self, unique_id: str):
        idx, worker = self.acquire()
        try:
            d = worker.driver
            d.get(f"http://127.0.0.1:{Config.FLASK_RUN_PORT}/quote/?id={unique_id}")
            WebDriverWait(d, 20).until(EC.presence_of_element_located((By.ID, "app")))
            app_el = d.find_element(By.ID, "app")
            # 收集所有占位元素（动图）相对 #app 的坐标与尺寸
            js = """
              const app = document.getElementById('app');
              const appRect = app.getBoundingClientRect();
              const list = [];
              app.querySelectorAll('[data-anim-id]').forEach(el => {
                const r = el.getBoundingClientRect();
                list.push({
                  id: el.getAttribute('data-anim-id'),
                  x: Math.round(r.left - appRect.left),
                  y: Math.round(r.top - appRect.top),
                  w: Math.round(r.width),
                  h: Math.round(r.height)
                });
              });
              return list;
            """
            boxes = d.execute_script(js)
            png = app_el.screenshot_as_png
            boxes_map = {b["id"]: (b["x"], b["y"], b["w"], b["h"]) for b in boxes}
            return png, boxes_map
        finally:
            self.release(idx)


class Screenshot:
    def __init__(self):
        self.pool = ScreenshotPool(Config.WORKER_POOL_SIZE)

    def __del__(self):
        try:
            self.pool.shutdown()
        except Exception:
            pass

    def screenshot(self, ret_type, unique_id):
        idx, worker = self.pool.acquire()
        try:
            d = worker.driver
            d.get(f"http://127.0.0.1:{Config.FLASK_RUN_PORT}/quote/?id={unique_id}")
            WebDriverWait(d, 20).until(EC.presence_of_element_located((By.ID, "app")))
            app_el = d.find_element(By.ID, "app")
            if ret_type == 'png':
                return app_el.screenshot_as_png
            elif ret_type == 'base64':
                return app_el.screenshot_as_base64
        finally:
            self.pool.release(idx)