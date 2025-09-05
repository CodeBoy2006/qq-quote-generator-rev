# =============================================================
# Stage 1: Build the Rust renderer (headless Blitz HTML)
# =============================================================
FROM rust:1.89-bullseye AS rust-builder

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates pkg-config git build-essential && \
    # --- THIS IS THE CORRECTED LINE (added a space) ---
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# --- CACHING STRATEGY ---
# 1. Copy only the manifest file.
COPY renderer/Cargo.toml ./renderer/

# 2. Create a dummy main.rs and fetch dependencies.
WORKDIR /build/renderer
RUN mkdir src && \
    printf "fn main() {}" > src/main.rs && \
    cargo fetch

# 3. Now copy the actual source code.
COPY renderer/src ./src

# 4. Build the release binary.
RUN cargo build --release


# =============================================================
# Stage 2: Final production image (Python app + our renderer)
# =============================================================
FROM python:3.11-slim-bullseye

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LITEHTML_RENDER_BIN=/app/litehtml_renderer

# Runtime libs for fonts (Blitz uses system fonts via fontconfig)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libfontconfig1 libfreetype6 \
    fonts-noto-cjk fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m appuser
WORKDIR /app

# Copy renderer binary (keep the original name/path to avoid app changes)
COPY --from=rust-builder /build/renderer/target/release/litehtml_renderer /app/litehtml_renderer

# Python deps layer (cache-friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Refresh font cache
RUN fc-cache -f -v

# Ownership & runtime
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000
# NOTE: Corrected original typo in bind address to 0.0.0.0:5000
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "main:app"]