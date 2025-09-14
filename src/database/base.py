"""Database base classes and configuration."""

# Import the modern SQLAlchemy 2.0 DeclarativeBase from models
# This ensures consistency across the codebase
from .models import Base

__all__ = ["Base"]
