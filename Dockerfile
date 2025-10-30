# RunPod Serverless Dockerfile for BeForward Parser Bot
# Use RunPod's official CUDA base (smaller and pre-optimized)
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    libgl1-mesa-glx \
    libglib2.0-0 \
    chromium-browser \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# CUDA environment variables for IOPaint
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# RunPod serverless handler
CMD ["python", "-u", "handler.py"]
