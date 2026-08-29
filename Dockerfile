# Production multi-stage Docker build for StreamPulse
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

# Install essential runtime system dependencies for OpenCV, PyTorch, and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .

# Install PyTorch CPU-optimized wheel followed by remaining packages
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-cache YOLOv8 Nano model weights during Docker build for offline instant startup
RUN python -c "from ultralytics import YOLO; model = YOLO('yolov8n.pt'); print('YOLOv8 Nano model pre-cached successfully')"

# Copy application source code
COPY . .

# Expose FastAPI HTTP/WebSocket port
EXPOSE 8000

# Default command starts the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
