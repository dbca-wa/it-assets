FROM python:3.6.6-slim-stretch
MAINTAINER asi@dbca.wa.gov.au

WORKDIR /usr/src/app
COPY . .
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir -r requirements.txt \
  && python manage.py collectstatic --noinput

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
EXPOSE 8080
CMD ["gunicorn", "itassets.wsgi", "--config", "gunicorn.ini"]
