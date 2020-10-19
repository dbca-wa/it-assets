# IT Assets System

This project consists of a Django application used by the Department of
Biodiversity, Conservation and Attractions to record and manage IT assets
and analytics.

# Installation

Create a new virtualenv and install required libraries using `pip`:

    pip install -r requirements.txt

# Environment variables

This project uses confy to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

# Unit tests

Start with `pip install coverage`. Run unit tests and obtain test coverage as follows:

    coverage run --source='.' manage.py test -k
    coverage report -m
