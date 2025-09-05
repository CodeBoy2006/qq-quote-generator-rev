# ======================================================================
# Stage 1: The Builder
# ======================================================================
FROM debian:bullseye AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config git ca-certificates \
    libcairo2-dev libpango1.0-dev libharfbuzz-dev libfontconfig1-dev \
    nlohmann-json3-dev && \
    rm -rf /var/lib/apt/lists/*

# Build and install litehtml (cached unless URL/revision changes)
WORKDIR /opt
RUN git clone https://github.com/litehtml/litehtml.git && \
    cd litehtml && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local && \
    make -j"$(nproc)" && \
    make install

# Build our native renderer
WORKDIR /app
COPY native/ ./native/
RUN mkdir -p /app/native/build && \
    cd /app/native/build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release && \
    make -j"$(nproc)"

# ======================================================================
# Stage 2: The Final Production Image
# ======================================================================
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Runtime deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libharfbuzz0b libfontconfig1 \
    fonts-noto-cjk fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser
WORKDIR /app

# Copy compiled binary and libs from builder
COPY --from=builder /app/native/build/litehtml_renderer /app/litehtml_renderer
COPY --from=builder /usr/local/lib/liblitehtml.so* /usr/local/lib/

# Update dynamic linker cache
RUN ldconfig

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Update font cache
RUN fc-cache -f -v

# Ownership
RUN chown -R appuser:appuser /app
USER appuser

# Expose & run
EXPOSE 5000
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "main:app"]