# Stage 1: Build dependencies (includes C toolchain for PyMuPDF)
FROM python:3.14-alpine AS build

ARG CACHE_BUST
RUN apk upgrade --no-cache && \
    apk add --no-cache \
    gcc \
    g++ \
    make \
    musl-dev \
    linux-headers \
    clang-dev \
    python3-dev \
    freetype-dev \
    harfbuzz-dev \
    jpeg-dev \
    openjpeg-dev \
    jbig2dec-dev \
    'zlib-dev>=1.3.2' \
    swig

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --no-cache-dir gunicorn

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached unless lock/pyproject changes)
COPY pyproject.toml uv.lock ./
RUN uv pip install --python /app/venv/bin/python -r pyproject.toml --extra server

# Install app
COPY src/ src/
RUN uv pip install --python /app/venv/bin/python --no-deps .

# Stage 2: Runtime image (no build tools)
FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

ARG CACHE_BUST
RUN apk upgrade --no-cache && \
    apk add --no-cache \
    freetype \
    harfbuzz \
    jpeg \
    openjpeg \
    jbig2dec \
    'zlib>=1.3.2' \
    libstdc++

RUN adduser -D -h /app appuser

WORKDIR /app

COPY --from=build /app/venv /app/venv

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 80

CMD gunicorn "voltaire.pdfservice.server.app:create_app()" \
    --bind 0.0.0.0:80 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}"
