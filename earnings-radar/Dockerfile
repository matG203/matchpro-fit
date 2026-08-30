FROM python:3.11-slim

# Deterministic logs and no .pyc clutter in the image layer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

WORKDIR /srv/earnings-radar

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Documentation only: the host assigns the real port via $PORT, which
# app.entrypoint reads. Binding 8000 unconditionally on Railway produces a
# container that starts cleanly and is never routed to.
EXPOSE 8000

CMD ["python", "-m", "app.entrypoint"]
