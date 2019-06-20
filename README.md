# IT Assets System

This project consists of a Django application used by the Department of
Biodiversity, Conservation and Attractions to record and manage IT assets.

# Installation

Create a new virtualenv and install required libraries using `pip`:

    pip install -r requirements.txt

# Environment variables

This project uses confy to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

Download of Freshdesk API data requires the following variables:

    FRESHDESK_ENDPOINT="https://dpaw.freshdesk.com/api/v2"
    FRESHDESK_API_KEY="VALID_API_KEY"

A link to the Alesco database table requires the following variables:

    ALESCO_DB_HOST
    ALESCO_DB_NAME
    ALESCO_DB_TABLE
    ALESCO_DB_USERNAME
    ALESCO_DB_PASSWORD

# Unit tests

Start with `pip install coverage`. Run unit tests and obtain test coverage as follows:

    coverage run --source='.' manage.py test -k
    coverage report -m
