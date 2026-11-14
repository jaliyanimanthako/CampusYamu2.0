"""CampusYamu public HTTP API (FastAPI). See campusyamu.api.app for the endpoints."""

from .app import create_app

__all__ = ["create_app"]
