FROM python:3.12-slim
WORKDIR /app

# Tells uv to compile .pyc bytecode files during the uv sync step
ENV UV_COMPILE_BYTECODE=1

# Install uv in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -LsSf https://astral.sh/uv/0.5.21/install.sh | sh && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /uv-installer.sh

# Ensure uv is in the PATH
ENV PATH="/root/.local/bin/:$PATH" 

COPY .python-version pyproject.toml uv.lock /app/

RUN uv sync

COPY app /app/app

ENTRYPOINT ["uv", "run", "uvicorn", "app.service:app", "--host", "0.0.0.0", "--port", "8000"]