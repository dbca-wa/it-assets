# syntax=docker/dockerfile:1
# Prepare the base environment.
FROM python:3.13-slim-bookworm AS builder_base

# This approximately follows this guide: https://hynek.me/articles/docker-uv/
# Which creates a standalone environment with the dependencies.
# - Silence uv complaining about not being able to use hard links,
# - tell uv to byte-compile packages for faster application startups,
# - prevent uv from accidentally downloading isolated Python builds,
# - pick a Python,
# - and finally declare `/app` as the target for `uv sync`.
ENV UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=1 \
  UV_PYTHON_DOWNLOADS=never \
  UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

# Since there's no point in shipping lock files, we move them
# into a directory that is NOT copied into the runtime image.
# The trailing slash makes COPY create `/_lock/` automagically.
COPY pyproject.toml uv.lock /_lock/

# Synchronize dependencies.
# This layer is cached until uv.lock or pyproject.toml change.
RUN --mount=type=cache,target=/root/.cache \
  cd /_lock && \
  uv sync \
  --frozen \
  --no-group dev

##################################################################################

FROM python:3.13-slim-bookworm
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/it-assets

# Install OS packages
RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends gdal-bin proj-bin libmagic-dev \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user.
RUN groupadd -r -g 1000 app \
  && useradd -r -u 1000 -d /app -g app -N app

COPY --from=builder_base --chown=app:app /app /app
# Make sure we use the virtualenv by default
# Run Python unbuffered
ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONUNBUFFERED=1

# Install the project.
WORKDIR /app
COPY gunicorn.py manage.py pyproject.toml ./
COPY itassets ./itassets
COPY registers ./registers
COPY organisation ./organisation
RUN python manage.py collectstatic --noinput
USER app
EXPOSE 8080
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.py"]
