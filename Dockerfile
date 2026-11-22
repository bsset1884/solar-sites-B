# het bouwen:  docker build -t solar .
# hoe je moet starten: docker run -p 8000:8000 solar        -> http://localhost:8000
# database bewaren tussen runs:  docker run -p 8000:8000 -v solar-data:/app/data solar

# ---- Fase 1: de React-app bouwen tot statische bestanden ----
FROM node:22-slim AS frontend
WORKDIR /frontend
# Eerst alleen de afhankelijkheden, zodat Docker deze laag hergebruikt als alleen de code verandert.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Fase 2: de Python-server die de API en die statisch bestanden serveert ----
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./static

# Draaien als gewone gebruiker in plaats van root; alleen de datamap is schrijfbaar
RUN useradd --create-home --uid 10001 solar \
    && mkdir -p /app/data \
    && chown solar /app/data
USER solar

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]