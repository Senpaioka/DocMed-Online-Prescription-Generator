FROM python:3.13-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install WeasyPrint system dependencies (Pango, Cairo, GDK-Pixbuf, LibFFI, Fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv from official binary image for fast, reliable builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python dependencies using uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Copy project source code
COPY . .

# Set default port
ENV PORT=10000
EXPOSE 10000

# Start production server using dynamic PORT environment variable
CMD ["sh", "-c", "uv run gunicorn manage:flask_app --bind 0.0.0.0:${PORT:-10000} --workers 2"]
