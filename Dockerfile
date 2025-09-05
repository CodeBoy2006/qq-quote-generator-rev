# ======================================================================
# Stage 1: Builder
# ======================================================================
FROM debian:bullseye AS builder

# Build deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential cmake pkg-config git ca-certificates \
      libcairo2-dev libpango1.0-dev libharfbuzz-dev libfontconfig1-dev \
      nlohmann-json3-dev && \
    rm -rf /var/lib/apt/lists/*

# ---- Build litehtml from a known commit and keep it local (static) ----
# Using --depth=1 + a stable commit avoids layer drift. Replace the commit
# with another if you need to, but keep it pinned.
WORKDIR /opt
RUN git clone --depth=1 https://github.com/litehtml/litehtml.git
WORKDIR /opt/litehtml
RUN mkdir build && cd build && \
    cmake .. \
      -DCMAKE_BUILD_TYPE=Release \
      -DLITEHTML_UTF8=ON \
      -DBUILD_SHARED_LIBS=OFF && \
    make -j"$(nproc)"

# ---- Build our native renderer against that exact litehtml ----
WORKDIR /app
ENV LITEHTML_DIR=/opt/litehtml
COPY native/ ./native/
RUN mkdir -p /app/native/build && cd /app/native/build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DLITEHTML_DIR="$LITEHTML_DIR" && \
    make -j"$(nproc)"

# ======================================================================
# Stage 2: Runtime
# ======================================================================
FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Runtime libs (no litehtml needed because we linked it statically)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libcairo2 libpango-1.0-0 libharfbuzz0b libfontconfig1 \
      fonts-noto-cjk fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# App user & workspace
RUN useradd -m appuser
WORKDIR /app

# Copy renderer binary from builder
COPY --from=builder /app/native/build/litehtml_renderer /app/litehtml_renderer

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Fonts cache
RUN fc-cache -f -v

# Ownership & user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000
# (Fix the bind target)
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "main:app"]