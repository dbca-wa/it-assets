# IT Assets System

This project consists of a Django application used by the Department of
Parks and Wildlife to record and manage IT assets.

# Installation

Create a new virtualenv and install required libraries using `pip`:

    pip install -r requirements.txt

# Environment variables

This project uses confy to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

Variables below may also need to be defined (context-dependent):

    DEBUG=True
    CSRF_COOKIE_SECURE=False
    SESSION_COOKIE_SECURE=False
    # debug-toolbar settings:
    INTERNAL_IP="x.x.x.x"

# Running

Use `runserver` to run a local copy of the application:

    python manage.py runserver 0.0.0.0:8080

Run console commands manually:

    python manage.py shell_plus
