# --- Stage 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
FROM python:3.11-slim-bullseye
ENV DEBIAN_FRONTEND=noninteractive

# 运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    fontconfig \
    gifsicle \
    wget unzip tar \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# geckodriver（固定版本更可复现）
ARG GECKODRIVER_VERSION=v0.34.0
RUN wget "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz" -O /tmp/geckodriver.tar.gz \
    && tar -C /usr/local/bin -xzf /tmp/geckodriver.tar.gz \
    && rm /tmp/geckodriver.tar.gz

# MiSans 字体
RUN wget "https://cdn.cnbj1.fds.api.mi-img.com/vipmlmodel/font/MiSans/MiSans.zip" -O /tmp/misans.zip \
    && unzip /tmp/misans.zip -d /tmp/misans \
    && mkdir -p /usr/local/share/fonts \
    && mv /tmp/misans/MiSans*/MiSans-Regular.ttf /usr/local/share/fonts/ \
    && fc-cache -fv \
    && rm -rf /tmp/misans.zip /tmp/misans

# 拷贝 Python 依赖
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 应用代码
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser
WORKDIR /app
COPY . .

# 入口脚本（新增）
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser
EXPOSE 5000

# 可调参数（也可在 docker run / compose 里覆盖）
ENV GUNICORN_WORKERS=4
ENV GUNICORN_TIMEOUT=120
ENV WORKER_POOL_SIZE=4

# 用入口脚本启动（支持环境变量展开 + 正确信号处理）
CMD ["/usr/local/bin/docker-entrypoint.sh"]