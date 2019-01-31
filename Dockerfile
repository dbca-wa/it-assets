FROM python:3.6.8-slim-stretch as builder
MAINTAINER asi@dbca.wa.gov.au

# Prepare the base environment.
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3-dev nmap \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install the project.
FROM builder
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt \
  && python manage.py collectstatic --noinput
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.ini"]
