# Use python-slim for a smaller image
FROM python:3.11-slim

# Install system dependencies (FFmpeg only)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements from the backend folder
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Copy backend and frontend folders
COPY backend ./backend
COPY frontend ./frontend

# Directorios para cache de modelos Whisper y descargas
ENV WHISPER_CACHE_DIR=/app/model
ENV FRONTEND_DIR=/app/frontend
RUN mkdir -p /app/model /app/backend/downloads

EXPOSE 10000

# Run uvicorn from within the backend folder to ensure correct path resolution
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
