# Multi-stage build following Astral's own uv-in-Docker guidance
# (https://docs.astral.sh/uv/guides/integration/docker/): dependencies are
# installed in their own layer, before the project's own source is even
# copied in, so an application-code change never busts the (comparatively
# slow) dependency-resolution cache. uv itself never ships in the final
# image, only the venv it built.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies only, from a bind mount rather than a COPY, so this layer's
# cache key is exactly the two files that determine it, nothing else. --no-dev
# excludes pytest/ruff: those belong in CI, never in the image that runs.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

# Now the project itself, installed non-editable: the final image runs
# against files baked into the venv, not a live source mount, so it behaves
# the same whether or not the build context still exists.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# Final stage: no uv, no build cache, no dev dependencies, just the venv this
# server actually runs from. Matches the builder's Debian codename (trixie)
# so glibc/libstdc++ line up between the two stages.
FROM python:3.14-slim AS final

# Runs as a fixed non-root uid so a compromised dependency can't write
# anywhere in the image; this server has no reason to write to disk at all.
RUN groupadd --system --gid 999 fhirmcp \
    && useradd --system --uid 999 --gid fhirmcp --no-create-home fhirmcp

WORKDIR /app
COPY --from=builder --chown=fhirmcp:fhirmcp /app/.venv /app/.venv
COPY --chown=fhirmcp:fhirmcp scripts/healthcheck.py ./scripts/healthcheck.py

ENV PATH="/app/.venv/bin:$PATH"

USER fhirmcp

# Documents the default; the real bind address is FHIR_MCP_HOST/FHIR_MCP_PORT
# from the environment (see config.py), set by docker-compose.yml for this
# service specifically, since the image itself stays agnostic to how it's run.
EXPOSE 3001

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "/app/scripts/healthcheck.py"]

CMD ["fhir-mcp"]
