FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.lock.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt

COPY backend ./backend
COPY data ./data
COPY scripts ./scripts
COPY --from=frontend-build /build/dist ./dist

RUN useradd --create-home --uid 10001 zhiji \
    && chown -R zhiji:zhiji /app

USER zhiji
EXPOSE 8000

CMD ["python", "-X", "utf8", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
