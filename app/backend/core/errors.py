"""Errors shared across the backend."""

from __future__ import annotations


class ConfigError(RuntimeError):
    """A required setting or file is missing. The message says how to fix it."""
