FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY visao/requirements.txt visao/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r visao/requirements.txt
COPY visao/modelos visao/modelos
COPY visao/vigia.yml visao/vigia.yml
COPY visao/vigia visao/vigia
COPY roteador/gerar.py roteador/gerar.py
COPY roteador/roteador.yml roteador/roteador.yml
COPY roteador/.env roteador/.env
COPY --from=frontend /app/frontend/dist frontend/dist
ENV PYTHONUNBUFFERED=1 VIGIA_AMBIENTE=prod-docker
WORKDIR /app/visao
EXPOSE 8000
CMD ["python", "-m", "vigia", "servir"]
