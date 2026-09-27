"""Web client: local FastAPI + Jinja2 + HTMX UI."""

from .app import create_app

__all__ = ["create_app"]
