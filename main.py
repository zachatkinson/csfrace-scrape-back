#!/usr/bin/env python3
"""
WordPress to Shopify Content Converter - Legacy Entry Point

This is the legacy entry point that redirects to the new async implementation.
For new development, use: python -m src.main

Author: CSFrace Development Team
License: MIT
"""

import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    # Import and run the new async main
    from src.main import main
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error importing async implementation: {e}")
    print("Please ensure all dependencies are installed:")
    print("  python -m pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error running converter: {e}")
    sys.exit(1)