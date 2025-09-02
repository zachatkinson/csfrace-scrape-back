"""Tests for database base module."""

import os
from datetime import UTC

import pytest
from sqlalchemy import Column, DateTime, Integer, String, text
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import sessionmaker

from src.database.base import Base


class TestDatabaseBase:
    """Test cases for database base functionality."""

    def _get_test_db_url(self):
        """Get PostgreSQL test database URL."""
        # Use environment variables or default PostgreSQL test configuration
        return (
            os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql+psycopg://postgres:postgres@localhost:5432/test_db"
        )

    def test_base_exists(self):
        """Test that Base is defined and accessible."""
        assert Base is not None

    def test_base_is_declarative_base(self):
        """Test that Base is a declarative base."""
        # Check that Base is created by declarative_base
        assert isinstance(Base, DeclarativeMeta)

    def test_base_has_metadata(self):
        """Test that Base has metadata attribute."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_registry_attribute(self):
        """Test that Base has registry attribute."""
        assert hasattr(Base, "registry")

    def test_base_can_be_subclassed(self):
        """Test that Base can be used as parent class for models."""

        # Create a test model that inherits from Base
        class TestModel(Base):
            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        # Should be able to create the class without error
        assert TestModel.__tablename__ == "test_model"
        assert hasattr(TestModel, "id")
        assert hasattr(TestModel, "name")

    def test_base_metadata_operations(self):
        """Test metadata operations on Base."""

        # Create a simple model
        class SimpleModel(Base):
            __tablename__ = "simple_model"
            id = Column(Integer, primary_key=True)

        # Test that metadata contains our table
        table_names = list(Base.metadata.tables.keys())
        assert "simple_model" in table_names

        # Clean up by removing the table from metadata
        Base.metadata.remove(Base.metadata.tables["simple_model"])

    def test_base_create_all(self, postgres_engine):
        """Test creating tables using Base.metadata.create_all."""
        # Use the postgres_engine fixture instead of creating our own
        engine = postgres_engine

        # Create a test model
        class CreateAllTest(Base):
            __tablename__ = "create_all_test"
            id = Column(Integer, primary_key=True)
            data = Column(String(100))

        try:
            # Should be able to create tables
            Base.metadata.create_all(engine, tables=[Base.metadata.tables["create_all_test"]])

            # Verify table was created by inspecting engine
            with engine.connect() as conn:
                # Try to query the table (will fail if it doesn't exist)
                result = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='create_all_test'"
                    )
                )
                tables = result.fetchall()
                assert len(tables) == 1
                assert tables[0][0] == "create_all_test"

        finally:
            # Clean up
            Base.metadata.remove(Base.metadata.tables["create_all_test"])
            postgres_engine.dispose()

    def test_base_drop_all(self, postgres_engine):
        """Test dropping tables using Base.metadata.drop_all."""
        # Use the postgres_engine fixture instead of creating our own
        engine = postgres_engine

        # Create a test model
        class DropAllTest(Base):
            __tablename__ = "drop_all_test"
            id = Column(Integer, primary_key=True)

        try:
            # Create the table first
            Base.metadata.create_all(engine, tables=[Base.metadata.tables["drop_all_test"]])

            # Drop the table
            Base.metadata.drop_all(engine, tables=[Base.metadata.tables["drop_all_test"]])

            # Verify table was dropped
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='drop_all_test'"
                    )
                )
                tables = result.fetchall()
                assert len(tables) == 0

        finally:
            # Clean up metadata
            Base.metadata.remove(Base.metadata.tables["drop_all_test"])
            postgres_engine.dispose()

    def test_base_with_session(self, postgres_engine):
        """Test using Base-derived models with SQLAlchemy sessions."""
        # Use the postgres_engine fixture
        engine = postgres_engine
        Session = sessionmaker(bind=engine)

        # Create test model
        class SessionTest(Base):
            __tablename__ = "session_test"
            id = Column(Integer, primary_key=True)
            value = Column(String(50))

        try:
            # Create table
            Base.metadata.create_all(engine, tables=[Base.metadata.tables["session_test"]])

            # Test session operations
            session = Session()

            # Create and save an instance
            instance = SessionTest(value="test_value")
            session.add(instance)
            session.commit()

            # Query the instance back
            queried = session.query(SessionTest).filter_by(value="test_value").first()
            assert queried is not None
            assert queried.value == "test_value"

            session.close()

        finally:
            # Clean up
            Base.metadata.remove(Base.metadata.tables["session_test"])
            postgres_engine.dispose()

    def test_base_table_inheritance(self):
        """Test that multiple models can inherit from Base."""

        class Model1(Base):
            __tablename__ = "model1"
            id = Column(Integer, primary_key=True)

        class Model2(Base):
            __tablename__ = "model2"
            id = Column(Integer, primary_key=True)

        try:
            # Both should be tracked in metadata
            assert "model1" in Base.metadata.tables
            assert "model2" in Base.metadata.tables

            # Models should be different classes
            assert Model1 != Model2
            assert Model1.__tablename__ != Model2.__tablename__

        finally:
            # Clean up
            if "model1" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["model1"])
            if "model2" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["model2"])

    def test_base_with_relationships(self, postgres_engine):
        """Test Base with models that have relationships."""
        from sqlalchemy import ForeignKey
        from sqlalchemy.orm import relationship

        class Parent(Base):
            __tablename__ = "parent"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            children = relationship("Child", back_populates="parent")

        class Child(Base):
            __tablename__ = "child"
            id = Column(Integer, primary_key=True)
            parent_id = Column(Integer, ForeignKey("parent.id"))
            parent = relationship("Parent", back_populates="children")

        try:
            # Should be able to create models with relationships
            assert hasattr(Parent, "children")
            assert hasattr(Child, "parent")

            # Use the provided engine
            Base.metadata.create_all(postgres_engine)

            Session = sessionmaker(bind=postgres_engine)
            session = Session()

            # Create parent and child with explicit relationship
            parent = Parent(name="Test Parent")
            child = Child()
            child.parent = parent  # Explicit bidirectional setup
            parent.children.append(child)

            session.add(parent)
            session.add(child)  # Explicitly add both objects
            session.commit()

            # Refresh and verify relationship works
            session.refresh(parent)
            assert len(parent.children) == 1
            assert parent.children[0].parent == parent

            # Also test queried objects
            queried_parent = session.query(Parent).first()
            session.refresh(queried_parent)  # Ensure lazy loading works
            assert len(queried_parent.children) == 1
            assert queried_parent.children[0].parent == queried_parent

            session.close()
            postgres_engine.dispose()

        finally:
            # Clean up
            for table_name in ["parent", "child"]:
                if table_name in Base.metadata.tables:
                    Base.metadata.remove(Base.metadata.tables[table_name])

    def test_base_with_complex_columns(self, postgres_engine):
        """Test Base with various column types and constraints."""
        from datetime import datetime

        from sqlalchemy import Boolean, Text, UniqueConstraint

        class ComplexModel(Base):
            __tablename__ = "complex_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False)
            description = Column(Text)
            is_active = Column(Boolean, default=True)
            created_at = Column(DateTime, default=lambda: datetime.now(UTC))

            __table_args__ = (UniqueConstraint("name", name="uq_complex_model_name"),)

        try:
            # Should create without error
            assert ComplexModel.__tablename__ == "complex_model"

            # Use the provided engine
            Base.metadata.create_all(postgres_engine)

            Session = sessionmaker(bind=postgres_engine)
            session = Session()

            # Create instance
            instance = ComplexModel(
                name="Test Complex", description="A complex test model", is_active=True
            )
            session.add(instance)
            session.commit()

            # Verify
            queried = session.query(ComplexModel).first()
            assert queried.name == "Test Complex"
            assert queried.is_active is True
            assert queried.created_at is not None

            session.close()
            postgres_engine.dispose()

        finally:
            if "complex_model" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["complex_model"])

    def test_base_metadata_consistency(self):
        """Test that Base.metadata remains consistent across operations."""
        initial_tables = set(Base.metadata.tables.keys())

        class ConsistencyTest(Base):
            __tablename__ = "consistency_test"
            id = Column(Integer, primary_key=True)

        try:
            # Should have one more table
            assert len(Base.metadata.tables) == len(initial_tables) + 1
            assert "consistency_test" in Base.metadata.tables

        finally:
            # Clean up
            Base.metadata.remove(Base.metadata.tables["consistency_test"])

        # Should be back to initial state
        assert len(Base.metadata.tables) == len(initial_tables)
        assert "consistency_test" not in Base.metadata.tables


class TestDatabaseBaseModule:
    """Test the database base module structure and imports."""

    def test_module_imports(self):
        """Test that required imports are available."""
        import src.database.base as base_module

        # Should have Base attribute
        assert hasattr(base_module, "Base")

        # Should be able to import declarative_base
        assert hasattr(base_module, "declarative_base")

    def test_base_is_singleton(self):
        """Test that Base behaves as a singleton across imports."""
        # Import again
        import src.database.base
        from src.database.base import Base as Base1

        Base2 = src.database.base.Base

        # Should be the same object
        assert Base1 is Base2

    def test_module_docstring(self):
        """Test that module has proper docstring."""
        import src.database.base

        assert src.database.base.__doc__ is not None
        assert "Database base classes" in src.database.base.__doc__

    def test_base_import_path(self):
        """Test that Base can be imported from expected path."""
        # Should be able to import Base directly
        from src.database.base import Base

        assert Base is not None

        # Should also work with module import
        import src.database.base

        assert src.database.base.Base is not None
        assert src.database.base.Base is Base


class TestDatabaseBaseEdgeCases:
    """Test edge cases and error conditions for database base."""

    def _get_test_db_url(self):
        """Get PostgreSQL test database URL."""
        # Use environment variables or default PostgreSQL test configuration
        return (
            os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql+psycopg://postgres:postgres@localhost:5432/test_db"
        )

    def test_base_with_invalid_tablename(self, postgres_engine):
        """Test behavior with invalid table names."""
        engine = postgres_engine

        class InvalidTable(Base):
            __tablename__ = ""  # Empty tablename should cause issues
            id = Column(Integer, primary_key=True)

        try:
            # The error occurs during table creation
            with pytest.raises(Exception):
                Base.metadata.create_all(engine, tables=[Base.metadata.tables[""]])
        finally:
            # Clean up the problematic table from metadata
            if "" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables[""])
            postgres_engine.dispose()

    def test_base_without_primary_key(self):
        """Test model without primary key."""

        # SQLAlchemy requires primary keys, so this should fail during class definition
        with pytest.raises(Exception):  # SQLAlchemy will raise ArgumentError

            class NoPrimaryKey(Base):
                __tablename__ = "no_primary_key"
                name = Column(String(50))

    def test_base_with_duplicate_tablename(self):
        """Test creating models with duplicate table names."""

        class FirstModel(Base):
            __tablename__ = "duplicate_name"
            id = Column(Integer, primary_key=True)

        try:
            # Second model with same tablename should cause error
            with pytest.raises(Exception):

                class SecondModel(Base):
                    __tablename__ = "duplicate_name"
                    id = Column(Integer, primary_key=True)

        finally:
            if "duplicate_name" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["duplicate_name"])

    def test_base_metadata_bound_engine(self, postgres_engine):
        """Test Base.metadata with bound engine."""
        engine = postgres_engine

        # Bind metadata to engine
        Base.metadata.bind = engine

        class BoundTest(Base):
            __tablename__ = "bound_test"
            id = Column(Integer, primary_key=True)

        try:
            # Should be able to create table (explicitly pass bind in modern SQLAlchemy)
            Base.metadata.create_all(bind=engine)

            # Verify table exists
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='bound_test'"
                    )
                )
                tables = result.fetchall()
                assert len(tables) == 1

        finally:
            # Clean up
            Base.metadata.bind = None
            if "bound_test" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["bound_test"])
            postgres_engine.dispose()


class TestDatabaseBaseIntegration:
    """Integration tests for database base functionality."""

    def _get_test_db_url(self):
        """Get PostgreSQL test database URL."""
        # Use environment variables or default PostgreSQL test configuration
        return (
            os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql+psycopg://postgres:postgres@localhost:5432/test_db"
        )

    def test_base_with_real_models(self, postgres_engine):
        """Test Base with models similar to actual application models."""
        from datetime import datetime

        from sqlalchemy import Boolean, Text

        class IntegrationJob(Base):
            __tablename__ = "integration_jobs"
            id = Column(Integer, primary_key=True)
            url = Column(String(500), nullable=False)
            status = Column(String(50), default="pending")
            created_at = Column(DateTime, default=lambda: datetime.now(UTC))
            updated_at = Column(
                DateTime,
                default=lambda: datetime.now(UTC),
                onupdate=lambda: datetime.now(UTC),
            )
            is_active = Column(Boolean, default=True)
            metadata_json = Column(Text)

        try:
            # Test database operations
            Base.metadata.create_all(postgres_engine)

            Session = sessionmaker(bind=postgres_engine)
            session = Session()

            # Create and save job
            job = IntegrationJob(
                url="https://example.com", status="pending", metadata_json='{"test": "data"}'
            )
            session.add(job)
            session.commit()

            # Query and verify
            queried_job = session.query(IntegrationJob).filter_by(url="https://example.com").first()
            assert queried_job is not None
            assert queried_job.status == "pending"
            assert queried_job.is_active is True
            assert queried_job.created_at is not None

            # Update job
            queried_job.status = "completed"
            session.commit()

            # Verify update
            updated_job = session.query(IntegrationJob).filter_by(id=queried_job.id).first()
            assert updated_job.status == "completed"

            session.close()
            postgres_engine.dispose()

        finally:
            if "integration_jobs" in Base.metadata.tables:
                Base.metadata.remove(Base.metadata.tables["integration_jobs"])

    def test_base_performance(self):
        """Test Base performance with many models."""
        import time

        start_time = time.time()

        # Create multiple models quickly
        models = []
        for i in range(50):
            class_name = f"PerformanceModel{i}"
            table_name = f"performance_model_{i}"

            model_class = type(
                class_name,
                (Base,),
                {
                    "__tablename__": table_name,
                    "id": Column(Integer, primary_key=True),
                    "data": Column(String(100)),
                },
            )
            models.append(model_class)

        creation_time = time.time() - start_time

        try:
            # Should be reasonably fast (less than 2 seconds)
            assert creation_time < 2.0

            # All models should be in metadata
            for i in range(50):
                assert f"performance_model_{i}" in Base.metadata.tables

        finally:
            # Clean up all performance models
            for i in range(50):
                table_name = f"performance_model_{i}"
                if table_name in Base.metadata.tables:
                    Base.metadata.remove(Base.metadata.tables[table_name])
