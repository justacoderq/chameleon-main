FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential cmake libgl1 libegl1 libglib2.0-0 fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-model.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-model.txt
COPY scripts/ ./scripts/
RUN python -m scripts.prepare_flan
COPY chameleon_design_schema_v0.9.json ./
COPY brand_kit/ ./brand_kit/
COPY renderer/ ./renderer/
COPY engine/ ./engine/
COPY evaluation/ ./evaluation/
ENV CHAMELEON_MODEL_MODE=required HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ENV CHAMELEON_MODEL_PATH=/app/models/flan-t5-small
RUN mkdir -p /app/input /app/output
ENTRYPOINT ["python", "-m", "engine.main"]
