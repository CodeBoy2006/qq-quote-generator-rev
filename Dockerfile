# ======================================================================
# Stage 1: The Builder - Compiles the C++ native renderer
# ======================================================================
FROM debian:bullseye AS builder

# Install C++ build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libharfbuzz-dev \
    libfontconfig1-dev \
    liblitehtml-dev \
    nlohmann-json3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the native source code
WORKDIR /app
COPY native/ ./native/

# Build the renderer
RUN mkdir -p /app/native/build && \
    cd /app/native/build && \
    cmake .. && \
    make -j$(nproc)

# The result of this stage is the compiled binary at /app/native/build/litehtml_renderer


# ======================================================================
# Stage 2: The Final Production Image
# ======================================================================
FROM python:3.11-slim-bullseye

# Set environment variables
# Tell Python not to buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Set the path for our native renderer binary
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Install runtime dependencies for Python app and C++ binary
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Runtime libs for the native renderer
    libcairo2 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    # Fonts are crucial for rendering!
    fonts-noto-cjk \
    fonts-noto-color-emoji && \
    # Update font cache so Pango/Fontconfig can find them
    fc-cache -f -v && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m appuser
WORKDIR /app

# Copy the compiled binary from the builder stage
COPY --from=builder /app/native/build/litehtml_renderer /app/litehtml_renderer

# Install Python dependencies
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership to the non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn for production
# The number of workers is a starting point, adjust based on your server's CPU cores (e.g., 2 * cores + 1)
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "main:app"]