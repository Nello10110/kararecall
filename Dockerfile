FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG PUID=10001
ARG PGID=10001
RUN groupadd --gid ${PGID} kararecall && useradd --uid ${PUID} --gid ${PGID} --no-create-home kararecall && mkdir -p /workspace/data /workspace/vault && chown -R kararecall:kararecall /workspace
ENV KARARECALL_ROOT=/workspace
COPY kararecall.py web_server.py settings.py integrations.py worker.py worker_media.py worker_documents.py web_research.py editorial.py publication.py usage.py controls.py reading.py ./
COPY digests.py digest_delivery.py digest_writer.py curation.py overview.py version.py ./
COPY source_enrichment.py content_support.py recovery.py ./
COPY web/ ./web/
COPY scripts/verify_storage.py ./verify_storage.py
COPY scripts/pilot.py ./pilot.py
USER kararecall

FROM base AS mcp
USER root
COPY kararecall_mcp.py requirements.mcp.txt ./
RUN pip install --no-cache-dir -r requirements.mcp.txt
USER kararecall
ENTRYPOINT ["python", "kararecall_mcp.py"]

FROM base AS worker
USER root
COPY requirements.worker.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.worker.txt
USER kararecall
HEALTHCHECK NONE
CMD ["python", "worker.py", "loop"]

FROM base AS web
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD python -c "import os,urllib.request,base64; u=os.environ.get('KARARECALL_USERNAME',''); p=os.environ.get('KARARECALL_PASSWORD',''); r=urllib.request.Request('http://127.0.0.1:8765/api/health'); r.add_header('Authorization','Basic '+base64.b64encode((u+':'+p).encode()).decode()) if u else None; urllib.request.urlopen(r,timeout=3)"
CMD ["python", "web_server.py", "--host", "0.0.0.0", "--port", "8765"]
