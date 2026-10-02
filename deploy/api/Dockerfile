# syntax=docker/dockerfile:1
#
# One backend image, three processes chosen by command:
#   API      python -m smb_requirement_agent.interfaces.api.serve --host 0.0.0.0
#   worker   python -m smb_requirement_agent.interfaces.worker
#   migrate  python -m smb_requirement_agent.infrastructure.persistence.migrate
# Build from the repository root: docker build -f deploy/api/Dockerfile .

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first, so a source change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER app
EXPOSE 8000 9464
CMD ["python", "-m", "smb_requirement_agent.interfaces.api.serve", "--host", "0.0.0.0", "--port", "8000"]
