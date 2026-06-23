# syntax=docker/dockerfile:1

# ---- Builder stage ----
FROM dhi.io/python:3.13-debian13-dev AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
  gdal-bin \
  proj-bin \
  libgdal36 \
  gcc \
  g++ \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync \
  --no-group dev \
  --link-mode=copy \
  --compile-bytecode \
  --no-python-downloads \
  --frozen \
  && rm -rf /bin/uv uv.lock

# ---- Runtime stage ----
FROM dhi.io/python:3.13-debian13-dev
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/it-assets

RUN apt-get update && apt-get install -y --no-install-recommends \
  gdal-bin \
  proj-bin \
  libgdal36 \
  # Run shared library linker after installing spatial packages
  && ldconfig \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"


WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app /app

# Copy the remaining project files to finish building the project
COPY --chown=nonroot:nonroot gunicorn.py manage.py pyproject.toml ./
COPY --chown=nonroot:nonroot itassets ./itassets
COPY --chown=nonroot:nonroot itsystems ./itsystems
COPY --chown=nonroot:nonroot organisation ./organisation
COPY --chown=nonroot:nonroot registers ./registers
# Compile scripts and collect static files
RUN python -m compileall manage.py itassets organisation itsystems registers \
  && python manage.py collectstatic --noinput

# Run the project as the nonroot user
USER nonroot
EXPOSE 8080
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.py"]
