# Prepare the base environment.
FROM python:3.10.12-slim-bookworm as builder_base_itassets
MAINTAINER asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source https://github.com/dbca-wa/it-assets

RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install -y libmagic-dev gcc binutils gdal-bin proj-bin python3-dev libpq-dev gzip curl \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install Python libs using Poetry.
FROM builder_base_itassets as python_libs_itassets
WORKDIR /app
ENV POETRY_VERSION=1.5.1
RUN pip install "poetry==$POETRY_VERSION"
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --only main

# Install the project.
FROM python_libs_itassets
COPY gunicorn.py manage.py ./
COPY itassets ./itassets
COPY registers ./registers
COPY nginx ./nginx
COPY rancher ./rancher
COPY bigpicture ./bigpicture
COPY organisation ./organisation

RUN python manage.py collectstatic --noinput

# Run the application as the www-data user.
USER www-data
EXPOSE 8080
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.py"]
