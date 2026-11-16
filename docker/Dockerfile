# CampusYamu web app image.
#   docker compose up --build            (see docker-compose.yml)
# Secrets come from .env at run time; nothing secret is baked into the image.

FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    CAMPUSYAMU_HOME=/app

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project
COPY src ./src
RUN uv sync --frozen

# Built frontend assets and app data.
COPY --from=frontend-build /frontend/dist ./frontend/dist
COPY config ./config
COPY data ./data

EXPOSE 8770 8780
CMD ["uv", "run", "--no-sync", "python", "-m", "campusyamu.web", "--host", "0.0.0.0", "--port", "8770"]
