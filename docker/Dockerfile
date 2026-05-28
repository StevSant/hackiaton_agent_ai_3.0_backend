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

COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
