# LivingMind demo backend. Build context is ./backend (see compose.yaml).
# Secrets are never copied in: DEEPSEEK_* and other settings come from the runtime environment.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build

# Versions are pinned by constraints.txt so an image built next month behaves like today's.
COPY requirements.txt requirements-dev.txt constraints.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-dev.txt -c constraints.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root: the demo backend never needs to write outside the image.
RUN useradd --create-home --uid 10001 livingmind
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=livingmind:livingmind app ./app
COPY --chown=livingmind:livingmind evals ./evals
COPY --chown=livingmind:livingmind scripts ./scripts
COPY --chown=livingmind:livingmind tests ./tests
COPY --chown=livingmind:livingmind pytest.ini ./pytest.ini

USER livingmind
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
