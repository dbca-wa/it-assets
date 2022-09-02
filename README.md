# IT Assets System

This project consists of a Django application used by the Department of
Biodiversity, Conservation and Attractions to record and manage IT assets
and analytics.

# Installation

The recommended way to set up this project for development is using
[Poetry](https://python-poetry.org/docs/) to install and manage a virtual Python
environment. With Poetry installed, change into the project directory and run:

    poetry install

To run Python commands in the virtualenv, thereafter run them like so:

    poetry run python manage.py

Manage new or updating project dependencies with Poetry also, like so:

    poetry add newpackage==1.0

# Environment variables

This project uses confy to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

# Running

Use `runserver` to run a local copy of the application:

    poetry run python manage.py runserver 0:8080

Run console commands manually:

    poetry run python manage.py shell_plus

# Unit tests

Start with `pip install coverage`. Run unit tests and obtain test coverage as follows:

    poetry run coverage run --source='.' manage.py test -k
    poetry run coverage report -m

# Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/it-assets .
