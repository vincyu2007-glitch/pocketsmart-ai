"""WSGI entry point for gunicorn / waitress / uWSGI.

    gunicorn "wsgi:application"
    waitress-serve --port=8080 wsgi:application
"""

from app import create_app

application = create_app()
app = application
