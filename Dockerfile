FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project

COPY src ./src

RUN uv sync \
    --frozen \
    --no-dev

RUN mkdir -p /app/data \
    && chown -R 10001:10001 /app/data

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "vector_pulse.gateway"]