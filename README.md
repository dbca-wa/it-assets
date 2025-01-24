# IT Assets System

This project consists of a Django application used by the Department of
Biodiversity, Conservation and Attractions to record and manage IT assets
and analytics.

## Installation

The recommended way to set up this project for development is using
[uv](https://docs.astral.sh/uv/)
to install and manage a Python virtual environment.
With uv installed, install the required Python version (see `pyproject.toml`). Example:

    uv python install 3.12

Change into the project directory and run:

    uv python pin 3.12
    uv sync

Activate the virtualenv like so:

    source .venv/bin/activate

To run Python commands in the activated virtualenv, thereafter run them like so:

    python manage.py

Manage new or updated project dependencies with uv also, like so:

    uv add newpackage==1.0

## Environment variables

This project uses confy to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

## Running

Use `runserver` to run a local copy of the application:

    python manage.py runserver 0:8080

Run console commands manually:

    python manage.py shell_plus

## Unit tests

Start with `pip install coverage`. Run unit tests and obtain test coverage as follows:

    coverage run --source='.' manage.py test -k
    coverage report -m

## Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/it-assets .

## Pre-commit hooks

This project includes the following pre-commit hooks:

- TruffleHog (credential scanning): <https://github.com/marketplace/actions/trufflehog-oss>

Pre-commit hooks may have additional system dependencies to run. Optionally
install pre-commit hooks locally like so (with the virtualenv activated first):

    pre-commit install

Reference: <https://pre-commit.com/>
