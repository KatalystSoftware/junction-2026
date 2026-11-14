# Since When: the app and its API in one image. Build context: projects/since-when/.
FROM node:24-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui ./
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libmariadb-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# The pinned versions are in uv.lock; torch comes from the CPU index named in pyproject.toml.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
ENV PATH=/app/.venv/bin:$PATH

COPY gapfinder gapfinder
COPY differences differences
COPY ui/fixtures ui/fixtures
COPY --from=ui /ui/dist ui/dist
ENV HF_HOME=/models PYTHONUNBUFFERED=1
CMD ["python", "-m", "gapfinder", "serve", "--host", "0.0.0.0", "--port", "8078"]
