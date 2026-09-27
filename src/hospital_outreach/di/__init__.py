"""Dependency injection: composition root for all accessors, DAO, and services."""

from .container import Container
from .providers import provide_container, provide_profile, provide_settings

__all__ = ["Container", "provide_container", "provide_profile", "provide_settings"]
