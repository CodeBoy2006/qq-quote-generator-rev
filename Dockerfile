# Use a slim Python base image which is Debian-based
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set environment variables to prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Install system dependencies, including Chinese fonts and emoji fonts
# This is the key fix for the font issue
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Install fonts
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    # Clean up to reduce image size
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker's layer cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Install Playwright browser and its Linux dependencies
# Running this as part of the build is more reliable than at runtime
RUN python setup_playwright.py

# Expose the port the app runs on
EXPOSE 5000

# Set the command to run the application using gunicorn for better performance, as recommended in the README
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]