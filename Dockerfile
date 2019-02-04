# Prepare the base environment.
FROM python:3.7.2-slim-stretch as builder_base
MAINTAINER asi@dbca.wa.gov.au
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Install some extra system libs required for this project.
FROM builder_base as builder_base_itassets
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y nmap \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install Python libs from requirements.txt.
FROM builder_base_itassets as python_libs_itassets
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the project.
FROM python_libs_itassets
WORKDIR /app
COPY assets ./assets
COPY frontend ./frontend
COPY itassets ./itassets
COPY knowledge ./knowledge
COPY organisation ./organisation
COPY recoup ./recoup
COPY registers ./registers
COPY status ./status
COPY tracking ./tracking
COPY webconfig ./webconfig
COPY __init__.py gunicorn.ini manage.py ./
RUN python manage.py collectstatic --noinput
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.ini"]
