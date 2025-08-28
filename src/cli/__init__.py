"""Command-line interface modules for CSFrace scraper.

This module provides CLI commands for various scraper operations including
batch processing, monitoring, and Grafana dashboard management.
"""

from .grafana_cli import app as grafana_app

__all__ = [
    "grafana_app",
]
