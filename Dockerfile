# Container image for server deployment (Fly.io, Render, or any other
# Docker host). Installs Tesseract OCR as a system package (the same
# local-OCR engine used everywhere else this app runs) -- no cloud OCR
# API involved.
FROM python:3.12-slim

# tesseract-ocr: the OCR engine itself. tesseract-ocr-eng: English trained
# data (the only language this app uses). libgl1 + libglib2.0-0: runtime
# libraries opencv-python-headless needs even without any GUI use.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The database and uploaded-photo temp files live on a volume mounted at
# /data (see fly.toml / render.yaml), so they survive redeploys instead of
# being wiped along with the container's own filesystem.
ENV DATABASE=/data/instance/app.sqlite3
ENV UPLOAD_FOLDER=/data/uploads
ENV PORT=8080

EXPOSE 8080

CMD ["python", "server.py"]
