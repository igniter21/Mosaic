FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[context]" \
    && useradd --create-home --uid 10001 mosaic \
    && mkdir -p /data \
    && chown -R 10001:10001 /data

USER mosaic

EXPOSE 8000

CMD ["uvicorn", "mosaic_memory_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
