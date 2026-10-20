# Chronicle MCP: local stdio MCP server for searching your AI chat history.
#
# Build:  docker build -t chronicle-mcp .
# Run:    docker run -i --rm -v "$HOME/.chronicle:/data" chronicle-mcp
#
# The server speaks MCP over stdin/stdout, so always run it with -i. Your chat
# archive lives in the /data volume; mount a host folder there to keep it.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHRONICLE_BASE_DIR=/data

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY chat_core.py chat_server.py cli.py ./
RUN pip install . \
    && useradd --create-home --uid 1000 chronicle \
    && mkdir -p /data \
    && chown chronicle:chronicle /data

USER chronicle
WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["chronicle-mcp-server"]
