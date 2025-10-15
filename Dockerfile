# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (psycopg, tzdata opcional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copie apenas o que for instalar primeiro para cache eficiente
COPY pyproject.toml requirements.txt* ./

# Se você usa requirements.txt:
RUN if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi

# Se você usa poetry/pdm, adapte aqui

# Copie o código
COPY . .

# Porta da app
EXPOSE 8000

# Variáveis default (podem ser sobrescritas no compose)
ENV EXECUTOR_MODE=read-only
ENV PROMETHEUS_URL=http://prometheus:9090
ENV GRAFANA_URL=http://grafana:3000

# Comando
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
