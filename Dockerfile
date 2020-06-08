# Prepare the base environment.
FROM python:3.7-slim-buster as builder_base_itassets
MAINTAINER asi@dbca.wa.gov.au
RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils gdal-bin proj-bin python3-dev \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install Python libs from requirements.txt.
FROM builder_base_itassets as python_libs_itassets
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the project.
FROM python_libs_itassets
COPY gunicorn.ini manage.py ./
COPY assets ./assets
COPY itassets ./itassets
COPY knowledge ./knowledge
COPY organisation ./organisation
COPY recoup ./recoup
COPY registers ./registers
COPY status ./status
COPY tracking ./tracking
COPY webconfig ./webconfig
COPY nginx ./nginx

COPY env ./.env
RUN python manage.py collectstatic --noinput
RUN rm .env

# Run the application as the www-data user.
USER www-data
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.ini"]
