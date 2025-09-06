# Dockerfile

# --- Stage 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

# Use -m to create the user's home directory, fixing the permission issue.
RUN groupadd -r appgroup && useradd --no-log-init -m -r -g appgroup appuser
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
FROM python:3.11-slim-bullseye
ENV DEBIAN_FRONTEND=noninteractive

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    fontconfig \
    gifsicle \
    wget \
    unzip \
    tar \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install geckodriver (WebDriver for Firefox)
# CHANGED: Updated version from v0.34.0 to v0.36.0 to match the latest firefox-esr
ARG GECKODRIVER_VERSION=v0.36.0
RUN wget "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz" -O /tmp/geckodriver.tar.gz \
    && tar -C /usr/local/bin -xzf /tmp/geckodriver.tar.gz \
    && rm /tmp/geckodriver.tar.gz

# Install MiSans font
RUN wget "https://cdn.cnbj1.fds.api.mi-img.com/vipmlmodel/font/MiSans/MiSans.zip" -O /tmp/misans.zip \
    && unzip /tmp/misans.zip -d /tmp/misans \
    && mkdir -p /usr/local/share/fonts \
    && mv /tmp/misans/MiSans*/MiSans-Regular.ttf /usr/local/share/fonts/ \
    && fc-cache -fv \
    && rm -rf /tmp/misans.zip /tmp/misans

# Copy the virtual environment with Python packages
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user and set up the app directory
# CHANGED: Use -m to create home directory, then also copy app files and set ownership.
RUN groupadd -r appgroup && useradd --no-log-init -m -r -g appgroup appuser
WORKDIR /app
COPY . .
# Also copy the entrypoint script and ensure it's executable
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R appuser:appgroup /app /home/appuser

USER appuser
EXPOSE 5000

# Environment variables for Gunicorn and the app (can be overridden)
ENV GUNICORN_WORKERS=2
ENV GUNICORN_TIMEOUT=120
ENV WORKER_POOL_SIZE=2

# Use the entrypoint script to start the service
CMD ["/usr/local/bin/docker-entrypoint.sh"]
