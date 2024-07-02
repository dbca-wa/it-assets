# syntax=docker/dockerfile:1
# Prepare the base environment.
FROM python:3.11.9-slim AS builder_base_itassets
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/it-assets

RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install -y libmagic-dev gcc binutils gdal-bin proj-bin python3-dev libpq-dev gzip \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --root-user-action=ignore --upgrade pip

# Temporary additional steps to mitigate CVE-2023-45853 (zlibg).
#WORKDIR /zlib
# Additional requirements to build zlibg
#RUN apt-get update -y \
#  && apt-get install -y wget build-essential make libc-dev \
#RUN wget -q https://zlib.net/zlib-1.3.1.tar.gz && tar xvzf zlib-1.3.1.tar.gz
#WORKDIR /zlib/zlib-1.3.1
#RUN ./configure --prefix=/usr/lib --libdir=/usr/lib/x86_64-linux-gnu \
# && make \
# && make install \
# && rm -rf /zlib

# Install Python libs using Poetry.
FROM builder_base_itassets AS python_libs_itassets
WORKDIR /app
ARG POETRY_VERSION=1.8.3
RUN pip install --root-user-action=ignore poetry=="${POETRY_VERSION}"
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --only main

# Create a non-root user.
ARG UID=10001
ARG GID=10001
RUN groupadd -g "${GID}" appuser \
  && useradd --no-create-home --no-log-init --uid "${UID}" --gid "${GID}" appuser

# Install the project.
FROM python_libs_itassets
COPY gunicorn.py manage.py ./
COPY itassets ./itassets
COPY registers ./registers
COPY organisation ./organisation
RUN python manage.py collectstatic --noinput

USER ${UID}
EXPOSE 8080
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.py"]
