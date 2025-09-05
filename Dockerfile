# ======================================================================
# Stage 1: The Builder - Compiles litehtml and our native renderer
# ======================================================================
FROM debian:bullseye AS builder

# Install C++ build dependencies, including git to clone litehtml
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    git \
    libcairo2-dev \
    libpango1.0-dev \
    libharfbuzz-dev \
    libfontconfig1-dev \
    # We remove liblitehtml-dev as we will build from source
    nlohmann-json3-dev && \
    rm -rf /var/lib/apt/lists/*

# --- NEW: Clone and build litehtml from source ---
WORKDIR /opt
RUN git clone https://github.com/litehtml/litehtml.git && \
    cd litehtml && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local && \
    make -j$(nproc) && \
    make install
# This installs litehtml headers, libraries, and CMake config to /usr/local
# ------------------------------------------------

# Copy our native source code
WORKDIR /app
COPY native/ ./native/

# Build our renderer (CMake will now find litehtml in /usr/local)
RUN mkdir -p /app/native/build && \
    cd /app/native/build && \
    cmake .. && \
    make -j$(nproc)


# ======================================================================
# Stage 2: The Final Production Image
# ======================================================================
FROM python:3.11-slim-bullseye

# Set environment variables (fixed legacy format)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Install runtime dependencies
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
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m appuser
WORKDIR /app

# Copy the compiled binaries and libraries from the builder stage
COPY --from=builder /app/native/build/litehtml_renderer /app/litehtml_renderer
COPY --from=builder /usr/local/lib/liblitehtml.so* /usr/local/lib/

# Update the dynamic linker cache to find the copied liblitehtml.so
RUN ldconfig

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Update font cache so Pango/Fontconfig can find the installed fonts
RUN fc-cache -f -v

# Change ownership to the non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn for production
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "main:app"]