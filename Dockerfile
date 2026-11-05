FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG PUID=10001
ARG PGID=10001
RUN groupadd --gid ${PGID} memoire && useradd --uid ${PUID} --gid ${PGID} --no-create-home memoire && mkdir -p /workspace/data /workspace/vault && chown -R memoire:memoire /workspace
ENV MEMOIRE_ROOT=/workspace
COPY cerveau.py web_server.py settings.py integrations.py worker.py worker_media.py publication.py usage.py ./
COPY web/ ./web/
COPY scripts/verify_storage.py ./verify_storage.py
USER memoire

FROM base AS worker
USER root
COPY requirements.worker.txt ./
RUN pip install --no-cache-dir -r requirements.worker.txt
USER memoire
HEALTHCHECK NONE
CMD ["python", "worker.py", "loop"]

FROM base AS web
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD python -c "import os,urllib.request,base64; u=os.environ.get('MEMOIRE_USERNAME',''); p=os.environ.get('MEMOIRE_PASSWORD',''); r=urllib.request.Request('http://127.0.0.1:8765/api/health'); r.add_header('Authorization','Basic '+base64.b64encode((u+':'+p).encode()).decode()) if u else None; urllib.request.urlopen(r,timeout=3)"
CMD ["python", "web_server.py", "--host", "0.0.0.0", "--port", "8765"]
