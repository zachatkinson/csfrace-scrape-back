#!/usr/bin/env python3
"""Debug health endpoint issues."""

import os
import traceback

import asyncio
from sqlalchemy import text

# Set required environment variables
os.environ.setdefault('SECRET_KEY', 'b18939e378f6b5e6c6f2ac8a7b3ee49eb3f5d6a909902abbdb4358a4093e2900')
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/csfrace_dev')

async def debug_health():
    """Debug health check components."""
    try:
        print("🔍 Debugging health check components...")

        # Import modules
        from src.api.dependencies import async_session
        from src.monitoring.health import health_checker
        from src.monitoring.observability import observability_manager

        print("✅ Modules imported successfully")

        # Test database connection
        print("\n📊 Testing database connection...")
        async with async_session() as db:
            result = await db.execute(text("SELECT 1"))
            print(f"✅ Database connection: {result.scalar()}")

        # Test health checker
        print("\n🏥 Testing health checker...")
        try:
            print("Running individual health checks...")
            results = await health_checker.run_all_checks()
            for name, result in results.items():
                print(f"  {name}: {result.status.value} - {result.message}")

            health_summary = health_checker.get_health_summary()
            print(f"✅ Health summary retrieved: {health_summary['status']}")
        except Exception as e:
            print(f"❌ Health checker failed: {e}")
            traceback.print_exc()

        # Test cache status
        print("\n💾 Testing cache status...")
        try:
            from src.caching.manager import cache_manager
            if cache_manager:
                await cache_manager.initialize()
                print("✅ Cache manager initialized")
            else:
                print("⚠️ Cache manager not available")
        except Exception as e:
            print(f"❌ Cache status failed: {e}")
            traceback.print_exc()

        # Test monitoring status
        print("\n📈 Testing monitoring status...")
        try:
            monitoring_status = observability_manager.get_component_status()
            print(f"✅ Monitoring status: {monitoring_status}")
        except Exception as e:
            print(f"❌ Monitoring status failed: {e}")
            traceback.print_exc()

        print("\n🎉 Debug complete!")

    except Exception as e:
        print(f"💥 Debug failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_health())
