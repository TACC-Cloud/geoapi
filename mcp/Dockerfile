FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY server.py ./
RUN pip install --no-cache-dir .

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8001 \
    GEOAPI_BASE_URL=http://geoapi:8000

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; \
        urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"MCP_PORT\",\"8001\")}/mcp', timeout=4)" \
        || exit 1

CMD ["python", "server.py"]
