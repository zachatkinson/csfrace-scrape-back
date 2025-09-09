#!/usr/bin/env python3
"""Create clean database schema directly from SQLAlchemy models."""

import os
from src.database.models import Base
from src.database.utils import get_database_url
from sqlalchemy import create_engine

def main():
    """Create all tables from SQLAlchemy models."""
    # Set required environment variables
    os.environ.setdefault('SECRET_KEY', 'b18939e378f6b5e6c6f2ac8a7b3ee49eb3f5d6a909902abbdb4358a4093e2900')
    os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/csfrace_dev')
    
    # Get database URL and create engine
    database_url = get_database_url()
    engine = create_engine(database_url, echo=True)
    
    print("Creating all tables from SQLAlchemy models...")
    Base.metadata.create_all(engine)
    print("✅ Database schema created successfully!")

if __name__ == "__main__":
    main()