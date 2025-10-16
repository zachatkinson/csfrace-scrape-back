#!/usr/bin/env python3
"""Script to remove all priority-related code from test files."""

import re
from pathlib import Path

# Files with priority references
test_files = [
    "tests/processors/test_metadata_extractor.py",
    "tests/plugins/test_registry.py",
    "tests/plugins/test_manager.py",
    "tests/plugins/test_base.py",
    "tests/integration/test_database_workflows.py",
    "tests/database/test_utils.py",
    "tests/database/test_queries.py",
    "tests/database/test_db_service.py",
    "tests/database/services/test_db_base.py",
    "tests/core/test_validation.py",
    "tests/caching/test_keys.py",
    "tests/api/test_crud.py",
    "tests/api/routers/test_user_settings.py",
    "tests/api/routers/jobs/test_execution.py",
    "tests/api/routers/jobs/test_control.py",
]

backend_root = Path("/Users/zach/Web Projects/csfrace-scrape/backend")

for test_file_path in test_files:
    file_path = backend_root / test_file_path
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        continue

    print(f"Processing: {test_file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    # Count priority references before
    priority_count_before = len(re.findall(r'priority', content, re.IGNORECASE))

    if priority_count_before == 0:
        print(f"  ✓ No priority references found")
        continue

    # Track changes
    lines_removed = 0

    # Remove JobPriority import
    content = re.sub(r'from src\.common\.status import JobPriority,?\s*', '', content)
    content = re.sub(r',\s*JobPriority', '', content)

    # Remove priority parameters from function signatures
    content = re.sub(r',?\s*priority:\s*[^,\)]+', '', content)

    # Remove priority dict entries
    content = re.sub(r'\s*"priority":\s*[^,\n]+,?\n?', '\n', content)
    content = re.sub(r'\s*priority=\s*[^,\n\)]+,?\n?', '\n', content)

    # Count priority references after
    priority_count_after = len(re.findall(r'priority', content, re.IGNORECASE))

    if priority_count_after < priority_count_before:
        # Write cleaned content
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✓ Removed {priority_count_before - priority_count_after} priority references")
    else:
        print(f"  ⚠ Still has {priority_count_after} priority references (manual cleanup needed)")

print("\n✅ Batch cleanup complete!")
