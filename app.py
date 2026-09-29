"""PocketSmart AI - Flask application factory.

Run locally:      python app.py
Run production:   gunicorn "app:create_app()" -w 2
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, render_template, session

from config import get_config
from security import get_csrf_token
from services.budget import format_inr
from services.gemini_client import build_client
from services.history import init_db
from views import web


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(get_config(config_name))

    logging.basicConfig(
        level=logging.DEBUG if app.config.get("DEBUG") else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    init_db(app.config["DATABASE_PATH"])

    app.secret_key = app.config["SECRET_KEY"]
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])
    app.register_blueprint(web)

    @app.context_processor
    def inject_globals():
        status = build_client(app.config).status
        return {
            "csrf_token": get_csrf_token(),
            "ai": status,
            "ai_status": status,
            "user_session_id": session.get("user_id"),
            "inr": format_inr,
            "app_name": "PocketSmart AI",
        }

    @app.template_filter("display_value")
    def _display_value(value):
        """Render arbitrary payload values safely in templates."""
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value)
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.cli.command("init-db")
    def cli_init_db() -> None:
        """Create the database tables."""
        init_db(app.config["DATABASE_PATH"])
        print(f"Initialised {app.config['DATABASE_PATH']}")

    @app.cli.command("ai-status")
    def cli_ai_status() -> None:
        """Show whether Gemini is configured, and list available models."""
        client = build_client(app.config)
        print(f"status: {client.status}")
        if not client.available:
            return
        try:
            for model in client.list_models():
                print(f"  {model['name']}")
        except Exception as exc:  # noqa: BLE001 - CLI diagnostics
            print(f"  could not list models: {exc}")

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, message=getattr(error, "description", "Bad request")), 400

    @app.errorhandler(404)
    def not_found(error):
        return (
            render_template(
                "error.html",
                code=404,
                message="We could not find that page. It may have been deleted.",
            ),
            404,
        )

    @app.errorhandler(429)
    def too_many(error):
        return (
            render_template(
                "error.html",
                code=429,
                message="Too many requests. Wait a minute, then try again.",
            ),
            429,
        )

    @app.errorhandler(413)
    def too_large(error):
        return (
            render_template(
                "error.html",
                code=413,
                message="That upload is too large. Keep images under the size limit shown on the form.",
            ),
            413,
        )

    @app.errorhandler(500)
    def server_error(error):  # pragma: no cover - exercised manually
        app.logger.exception("Unhandled error: %s", error)
        return (
            render_template(
                "error.html",
                code=500,
                message="Something broke on our side. Please try again.",
            ),
            500,
        )


app = create_app(os.getenv("FLASK_ENV") or None)


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes"},
    )
