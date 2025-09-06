# Dockerfile

# --- Stage 1: Builder ---
#
# Build Python dependencies in a separate stage to keep the final image clean.
# This also caches the dependencies unless requirements.txt changes.
FROM python:3.11-slim-bullseye AS builder

# Set up a non-root user for the build stage
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Create and activate a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
#
# Build the final, optimized image for production.
FROM python:3.11-slim-bullseye

# Set environment variables for non-interactive installs
ENV DEBIAN_FRONTEND=noninteractive

# Install system runtime dependencies:
# - firefox-esr: The headless browser
# - fontconfig: For font management
# - gifsicle: Optional, for GIF optimization
# - wget, unzip, tar: For downloading assets during build
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    fontconfig \
    gifsicle \
    wget \
    unzip \
    tar \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install geckodriver (WebDriver for Firefox)
# We use a specific version for build reproducibility, unlike the CI's "latest".
ARG GECKODRIVER_VERSION=v0.34.0
RUN wget "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz" -O /tmp/geckodriver.tar.gz \
    && tar -C /usr/local/bin -xzf /tmp/geckodriver.tar.gz \
    && rm /tmp/geckodriver.tar.gz

# Install MiSans font (from the CI script)
RUN wget "https://cdn.cnbj1.fds.api.mi-img.com/vipmlmodel/font/MiSans/MiSans.zip" -O /tmp/misans.zip \
    && unzip /tmp/misans.zip -d /tmp/misans \
    && mkdir -p /usr/local/share/fonts \
    && mv /tmp/misans/MiSans*/MiSans-Regular.ttf /usr/local/share/fonts/ \
    && fc-cache -fv \
    && rm -rf /tmp/misans.zip /tmp/misans

# Copy the virtual environment with Python packages from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user and set up the app directory
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser
WORKDIR /app
COPY . .
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Set default Gunicorn configurations (can be overridden with -e)
ENV GUNICORN_WORKERS=4
ENV GUNICORN_TIMEOUT=120

# Run the application using Gunicorn for production
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "$GUNICORN_WORKERS", \
     "--timeout", "$GUNICORN_TIMEOUT", \
     "main:app"]