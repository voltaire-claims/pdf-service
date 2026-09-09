# Stage 1: Install dependencies using PyMuPDF's manylinux wheels.
# Match voltaire-app's glibc DHI images: Alpine requires a PyMuPDF source
# build, which fails before metadata generation on arm64.
FROM dhi.io/python:3.14-dev AS build

COPY --from=dhi.io/uv:0 /usr/local/bin/uv /usr/local/bin/uv

RUN uv venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT=/app/venv

WORKDIR /app

# Install dependencies (cached unless lock/pyproject changes)
COPY pyproject.toml uv.lock ./
ARG CACHE_BUST
RUN uv sync --locked --no-dev --extra server --no-install-project && \
    uv pip install --python /app/venv/bin/python gunicorn

# Install app
COPY src/ src/
RUN uv pip install --python /app/venv/bin/python --no-deps .

# The minimal runtime has no OS package manager. Copy the shared libraries
# needed by PyMuPDF and other native wheels, as in voltaire-app.
RUN mkdir -p /opt/runtime-libs && \
    find /app/venv/lib -name "*.so*" -print0 | \
    xargs -0 -r ldd | \
    awk '$3 ~ "^/usr/lib/" { print $3 } $1 ~ "^/usr/lib/" { print $1 }' | \
    sort -u | \
    while read -r lib; do \
        mkdir -p "/opt/runtime-libs$(dirname "$lib")"; \
        cp -L "$lib" "/opt/runtime-libs$lib"; \
    done

# Stage 2: Runtime image (no shell, OS package manager, or build tools)
FROM dhi.io/python:3.14

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"
ENV HOME=/tmp
ENV TMPDIR=/tmp

WORKDIR /app

COPY --from=build --chown=0:0 /app/venv /app/venv
COPY --from=build --chown=0:0 /opt/runtime-libs/ /
COPY --chown=0:0 gunicorn.conf.py /app/gunicorn.conf.py

USER 65532

# Check native links and temporary-file access as the runtime user.
RUN ["python", "-c", "import os, pymupdf; path = '/tmp/pymupdf-runtime-check.pdf'; doc = pymupdf.open(); page = doc.new_page(); page.insert_text((72, 72), 'runtime check'); doc.save(path); reopened = pymupdf.open(path); assert reopened.page_count == 1; assert 'runtime check' in reopened[0].get_text(); reopened.close(); doc.close(); os.remove(path)"]

# PyMuPDF's image conversion uses Pillow and its native image codecs.
RUN ["python", "-c", "import io, pymupdf; from PIL import Image; doc = pymupdf.open(); page = doc.new_page(); pix = page.get_pixmap(); Image.open(io.BytesIO(pix.pil_tobytes(format='PNG'))).load(); Image.open(io.BytesIO(pix.pil_tobytes(format='JPEG'))).load(); doc.close()"]

EXPOSE 80

CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "voltaire.pdfservice.server.app:create_app()"]
