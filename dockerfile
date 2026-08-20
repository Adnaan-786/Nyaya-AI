FROM python:3.12-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs appear immediately
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# System packages needed by the Tesseract OCR fallback (module M6):
# tesseract-ocr does the actual OCR; poppler-utils (pdftoppm) is what
# pdf2image shells out to for rasterizing scanned PDF pages before OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better Docker cache)
COPY pyproject.toml uv.lock ./

COPY README.md ./

# copy project source BEFORE uv sync
COPY app ./app

# Install dependencies
RUN uv sync --frozen --no-dev
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy application
COPY . .

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]