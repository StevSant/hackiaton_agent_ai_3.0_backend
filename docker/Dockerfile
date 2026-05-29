FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# sentence-transformers pulls torch with CUDA wheels by default (~1.5 GB of
# nvidia/* packages we never use on Cloud Run). Reinstall torch from the
# CPU-only index in-place. Once pyproject.toml declares [tool.uv.sources]
# torch = { index = "pytorch-cpu" } we can drop this step.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv/bin/python --reinstall \
        --index-url https://download.pytorch.org/whl/cpu \
        torch && \
    find /app/.venv -depth -type d \( \
        -name 'nvidia*' -o \
        -name 'cuda*' -o \
        -name 'cublas*' -o \
        -name 'cudnn*' -o \
        -name 'nccl*' -o \
        -name 'triton' \
    \) -exec rm -rf {} + && \
    find /app/.venv -depth -type d \( \
        -name 'tests' -o \
        -name 'test' -o \
        -name '__pycache__' \
    \) -exec rm -rf {} + && \
    find /app/.venv -type f -name '*.pyc' -delete


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# LightGBM's wheel dynamically links libgomp (OpenMP runtime), which python:3.12-slim
# omits. Without it `lgb.Booster(...)` raises "libgomp.so.1: cannot open shared object
# file", the V4 classifier load fails silently and the UI shows "Modelo no cargado"
# (sklearn's V5 anomaly model has no such dependency, which is why it loaded fine).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
