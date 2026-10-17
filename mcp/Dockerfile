FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY server.py ./
RUN pip install --no-cache-dir .

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8001 \
    GEOAPI_BASE_URL=http://geoapi:8000

EXPOSE 8001

CMD ["python", "server.py"]
