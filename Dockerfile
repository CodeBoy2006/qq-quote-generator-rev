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

# --- OPTIMIZATION: Build litehtml in its own separate step ---
# This layer will be cached as long as the git repo URL doesn't change.
# Subsequent builds will be much faster.
WORKDIR /opt
RUN git clone https://github.com/litehtml/litehtml.git && \
    cd litehtml && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local && \
    make -j$(nproc) && \
    make install

# Now, build our application's native renderer
WORKDIR /app
COPY native/ ./native/
RUN mkdir -p /app/native/build && \
    cd /app/native/build && \
    cmake .. && \
    make -j$(nproc)

# ======================================================================
# Stage 2: The Final Production Image
# ======================================================================
FROM python:3.11-slim-bullseye

# (The rest of the Dockerfile remains exactly the same as before)
# ... [Omitted for brevity, no changes needed here] ...

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libharfbuzz0b libfontconfig1 \
    fonts-noto-cjk fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m appuser
WORKDIR /app

# Copy the compiled binaries and libraries from the builder stage
COPY --from=builder /app/native/build/litehtml_renderer /app/litehtml_renderer
COPY --from=builder /usr/local/lib/liblitehtml.so* /usr/local/lib/

# Update the dynamic linker cache
RUN ldconfig

# Install Python dependencies (copying requirements.txt first for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Update font cache
RUN fc-cache -f -v

# Change ownership
RUN chown -R appuser:appuser /app
USER appuser

# Expose port and run
EXPOSE 5000
CMD ["gunicorn", "--workers", "4", "--bind", "0.-", "main:app"]