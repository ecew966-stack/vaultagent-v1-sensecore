FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY demo ./demo
COPY configs ./configs
COPY data ./data
COPY scripts ./scripts
RUN pip install --upgrade pip && pip install -e ".[demo]"
RUN useradd --create-home --uid 10001 vaultagent && mkdir -p /app/state && \
    chown -R vaultagent:vaultagent /app
USER vaultagent
EXPOSE 8080 8501
