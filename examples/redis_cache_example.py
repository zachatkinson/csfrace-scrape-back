#!/usr/bin/env python3
"""
Example demonstrating Redis cache usage with the WordPress to Shopify converter.

Prerequisites:
1. Install Redis: brew install redis (macOS) or apt-get install redis (Ubuntu)
2. Start Redis server: redis-server
3. Install Redis Python client: pip install redis>=5.0.0
"""

import asyncio
from pathlib import Path

from src.caching.manager import CacheManager
from src.caching.base import CacheConfig, CacheBackend


async def redis_cache_example():
    """Demonstrate Redis caching functionality."""
    
    print("🔄 Redis Cache Example")
    print("=" * 50)
    
    # Configure Redis cache
    config = CacheConfig(
        backend=CacheBackend.REDIS,
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        redis_key_prefix="wp-shopify:",
        ttl_html=1800,  # 30 minutes
        ttl_images=86400,  # 24 hours
        compress=True
    )
    
    cache = CacheManager(config)
    
    try:
        # Initialize cache (will connect to Redis)
        print("🔗 Connecting to Redis...")
        await cache.initialize()
        print("✅ Redis connection established!")
        
        # Test URL and content
        test_url = "https://csfrace.com/blog/sample-post"
        test_html = """
        <html>
        <head>
            <title>Sample Blog Post</title>
            <meta name="description" content="A sample WordPress post">
        </head>
        <body>
            <h1>Welcome to CSFrace</h1>
            <p>This is sample content from WordPress.</p>
            <img src="https://example.com/image.jpg" alt="Sample Image">
        </body>
        </html>
        """
        
        # Cache HTML content
        print(f"💾 Caching HTML content for {test_url}...")
        success = await cache.set_html(test_url, test_html)
        print(f"   Success: {success}")
        
        # Cache metadata
        metadata = {
            "title": "Sample Blog Post",
            "description": "A sample WordPress post",
            "author": "CSFrace Team",
            "published_date": "2025-08-25",
            "tags": ["wordpress", "shopify", "migration"]
        }
        
        print("📋 Caching metadata...")
        await cache.set_metadata(test_url, metadata)
        
        # Cache robots.txt
        robots_content = """
        User-agent: *
        Disallow: /wp-admin/
        Allow: /wp-content/uploads/
        Sitemap: https://csfrace.com/sitemap.xml
        """
        
        print("🤖 Caching robots.txt...")
        await cache.set_robots_txt("csfrace.com", robots_content)
        
        # Retrieve cached data
        print("\n🔍 Retrieving cached data...")
        
        cached_html = await cache.get_html(test_url)
        print(f"   HTML cache hit: {cached_html is not None}")
        
        cached_metadata = await cache.get_metadata(test_url)
        print(f"   Metadata cache hit: {cached_metadata is not None}")
        print(f"   Title: {cached_metadata.get('title', 'N/A') if cached_metadata else 'N/A'}")
        
        cached_robots = await cache.get_robots_txt("csfrace.com")
        print(f"   Robots.txt cache hit: {cached_robots is not None}")
        
        # Show cache statistics
        print("\n📊 Cache Statistics:")
        stats = await cache.get_cache_stats()
        
        print(f"   Backend: {stats['backend']}")
        print(f"   Total entries: {stats['total_entries']}")
        print(f"   Cache size: {stats['total_size_mb']} MB")
        print(f"   Hit rate: {stats['hit_rate']:.1f}%")
        print(f"   Redis version: {stats.get('redis_version', 'unknown')}")
        print(f"   Redis memory used: {stats.get('redis_memory_used', 'unknown')}")
        
        # Test cache invalidation
        print("\n🗑️  Testing cache invalidation...")
        invalidated = await cache.invalidate_url(test_url)
        print(f"   Invalidated: {invalidated}")
        
        # Verify invalidation
        cached_html_after = await cache.get_html(test_url)
        print(f"   HTML after invalidation: {cached_html_after is not None}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Redis server is running: redis-server")
        print("2. Install Redis client: pip install redis>=5.0.0")
        print("3. Check Redis connection: redis-cli ping")
        
    finally:
        # Cleanup
        await cache.shutdown()
        print("\n🏁 Redis cache example completed!")


async def file_cache_comparison():
    """Show file cache for comparison."""
    print("\n📁 File Cache Comparison")
    print("=" * 30)
    
    config = CacheConfig(
        backend=CacheBackend.FILE,
        cache_dir=Path("example_cache"),
        ttl_html=1800,
        compress=True
    )
    
    cache = CacheManager(config)
    await cache.initialize()
    
    # Same operations as Redis example
    test_url = "https://csfrace.com/blog/sample-post"
    test_html = "<html><body>File cache test</body></html>"
    
    await cache.set_html(test_url, test_html)
    cached = await cache.get_html(test_url)
    
    stats = await cache.get_cache_stats()
    print(f"   File cache entries: {stats['total_entries']}")
    print(f"   Cache directory: {stats.get('cache_dir', 'unknown')}")
    
    await cache.shutdown()
    
    # Cleanup
    import shutil
    shutil.rmtree("example_cache", ignore_errors=True)


if __name__ == "__main__":
    print("WordPress to Shopify Converter - Caching Examples\n")
    
    asyncio.run(redis_cache_example())
    asyncio.run(file_cache_comparison())