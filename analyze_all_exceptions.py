#!/usr/bin/env python3
"""
Comprehensive Exception Analysis for AUDIT_2.md Compliance
Analyzes ALL exception handling patterns to identify DRY violations
"""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExceptionPattern:
    file_path: str
    line_number: int
    function_name: str
    exception_type: str
    has_decorator: bool
    pattern_type: str  # 'database', 'http', 'cache', 'auth', 'legitimate', 'unclear'
    code_context: str
    violation_type: str = ""


class ExceptionAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.patterns: list[ExceptionPattern] = []
        self.current_function = None
        self.function_decorators: set[str] = set()

    def visit_FunctionDef(self, node):
        # Track current function and its decorators
        old_function = self.current_function
        old_decorators = self.function_decorators.copy()

        self.current_function = node.name
        self.function_decorators = set()

        # Collect decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self.function_decorators.add(decorator.id)
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                self.function_decorators.add(decorator.func.id)

        self.generic_visit(node)

        # Restore previous function context
        self.current_function = old_function
        self.function_decorators = old_decorators

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Try(self, node):
        # Analyze try/except patterns
        for handler in node.handlers:
            exception_type = "Exception"
            if handler.type:
                if isinstance(handler.type, ast.Name):
                    exception_type = handler.type.id
                elif isinstance(handler.type, ast.Attribute):
                    exception_type = f"{handler.type.value.id if hasattr(handler.type.value, 'id') else 'unknown'}.{handler.type.attr}"
                elif isinstance(handler.type, ast.Tuple):
                    # Multiple exception types
                    types = []
                    for elt in handler.type.elts:
                        if isinstance(elt, ast.Name):
                            types.append(elt.id)
                    exception_type = f"({', '.join(types)})"

            # Get code context
            try:
                with open(self.file_path) as f:
                    lines = f.readlines()
                    start_line = max(0, node.lineno - 3)
                    end_line = min(len(lines), node.end_lineno + 2)
                    context = "".join(lines[start_line:end_line]).strip()
            except Exception:
                context = "Unable to read context"

            # Determine pattern type
            pattern_type = self.classify_pattern(exception_type, context, handler)

            # Check if function has appropriate decorator
            has_decorator = self.has_appropriate_decorator(pattern_type)

            pattern = ExceptionPattern(
                file_path=self.file_path,
                line_number=node.lineno,
                function_name=self.current_function or "module_level",
                exception_type=exception_type,
                has_decorator=has_decorator,
                pattern_type=pattern_type,
                code_context=context,
            )

            # Determine violation type
            if pattern_type in ["database", "http", "cache", "auth"] and not has_decorator:
                pattern.violation_type = f"Missing @{pattern_type}_error_handler decorator"
            elif pattern_type == "unclear":
                pattern.violation_type = "Needs manual review"

            self.patterns.append(pattern)

        self.generic_visit(node)

    def classify_pattern(self, exception_type: str, context: str, handler) -> str:
        """Classify the exception pattern type"""
        context_lower = context.lower()

        # Database patterns
        if any(
            keyword in context_lower
            for keyword in [
                "sqlalchemy",
                "database",
                "db.",
                "session.",
                "execute",
                "commit",
                "rollback",
                "query",
                "select",
                "insert",
                "update",
                "delete",
                "psycopg2",
                "asyncpg",
            ]
        ):
            return "database"

        if any(
            exc in exception_type
            for exc in ["SQLAlchemyError", "DatabaseError", "IntegrityError", "OperationalError"]
        ):
            return "database"

        # HTTP patterns
        if any(
            keyword in context_lower
            for keyword in [
                "request",
                "response",
                "aiohttp",
                "httpx",
                "requests",
                "fetch",
                "get(",
                "post(",
                "put(",
                "delete(",
                "patch(",
                "session.",
                "client.",
                "timeout",
                "connection",
            ]
        ):
            return "http"

        if any(
            exc in exception_type
            for exc in [
                "HTTPError",
                "RequestException",
                "Timeout",
                "ConnectionError",
                "ClientError",
            ]
        ):
            return "http"

        # Cache patterns
        if any(
            keyword in context_lower
            for keyword in ["cache", "redis", "memcached", "get_cache", "set_cache", "cache_key"]
        ):
            return "cache"

        if any(exc in exception_type for exc in ["RedisError", "CacheError", "ConnectionError"]):
            return "cache"

        # Auth patterns
        if any(
            keyword in context_lower
            for keyword in [
                "auth",
                "token",
                "jwt",
                "login",
                "logout",
                "oauth",
                "permission",
                "user",
            ]
        ):
            return "auth"

        if any(
            exc in exception_type
            for exc in ["AuthenticationError", "AuthorizationError", "TokenError"]
        ):
            return "auth"

        # Legitimate patterns (infrastructure/framework)
        if any(
            keyword in context_lower
            for keyword in [
                "importerror",
                "modulenotfounderror",
                "keyboardinterrupt",
                "systemexit",
                "filenotfounderror",
                "json.",
                "yaml.",
                "configparser",
                "pydantic",
                "validation",
                "environment",
                "startup",
                "shutdown",
            ]
        ):
            return "legitimate"

        if any(
            exc in exception_type
            for exc in [
                "ImportError",
                "ModuleNotFoundError",
                "KeyboardInterrupt",
                "SystemExit",
                "FileNotFoundError",
                "JSONDecodeError",
                "ValidationError",
                "ValueError",
                "TypeError",
                "AttributeError",
                "KeyError",
            ]
        ):
            return "legitimate"

        return "unclear"

    def has_appropriate_decorator(self, pattern_type: str) -> bool:
        """Check if function has appropriate error handling decorator"""
        if pattern_type == "database":
            return "database_error_handler" in self.function_decorators
        elif pattern_type == "http":
            return any(
                dec in self.function_decorators
                for dec in ["api_error_handler", "http_error_handler"]
            )
        elif pattern_type == "cache":
            return "cache_error_handler" in self.function_decorators
        elif pattern_type == "auth":
            return "auth_error_handler" in self.function_decorators

        return True  # Legitimate patterns don't need decorators


def analyze_file(file_path: str) -> list[ExceptionPattern]:
    """Analyze a single Python file for exception patterns"""
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)

        analyzer = ExceptionAnalyzer(file_path)
        analyzer.visit(tree)
        return analyzer.patterns
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


def main():
    """Main analysis function"""
    backend_src = Path("/Users/zach/Web Projects/csfrace-scrape/backend/src")

    all_patterns = []

    # Analyze all Python files
    for py_file in backend_src.rglob("*.py"):
        patterns = analyze_file(str(py_file))
        all_patterns.extend(patterns)

    # Categorize results
    violations = [p for p in all_patterns if p.violation_type]
    legitimate = [
        p for p in all_patterns if p.pattern_type == "legitimate" and not p.violation_type
    ]
    needs_review = [p for p in all_patterns if p.pattern_type == "unclear"]

    print("=" * 80)
    print("COMPREHENSIVE EXCEPTION ANALYSIS - AUDIT_2.md COMPLIANCE")
    print("=" * 80)

    print(f"\nTOTAL EXCEPTION PATTERNS FOUND: {len(all_patterns)}")
    print(f"VIOLATIONS REQUIRING FIXES: {len(violations)}")
    print(f"LEGITIMATE PATTERNS: {len(legitimate)}")
    print(f"PATTERNS NEEDING MANUAL REVIEW: {len(needs_review)}")

    # Violations by type
    violation_types = {}
    for v in violations:
        pattern_type = v.pattern_type
        if pattern_type not in violation_types:
            violation_types[pattern_type] = []
        violation_types[pattern_type].append(v)

    print("\n" + "=" * 60)
    print("VIOLATIONS BY TYPE (MUST BE FIXED)")
    print("=" * 60)

    for vtype, patterns in violation_types.items():
        print(f"\n{vtype.upper()} VIOLATIONS: {len(patterns)}")
        print("-" * 40)
        for p in patterns:
            rel_path = p.file_path.replace("/Users/zach/Web Projects/csfrace-scrape/backend/", "")
            print(f"  {rel_path}:{p.line_number} in {p.function_name}()")
            print(f"    Exception: {p.exception_type}")
            print(f"    Fix: {p.violation_type}")
            print()

    print("\n" + "=" * 60)
    print("PATTERNS NEEDING MANUAL REVIEW")
    print("=" * 60)

    for p in needs_review:
        rel_path = p.file_path.replace("/Users/zach/Web Projects/csfrace-scrape/backend/", "")
        print(f"\n{rel_path}:{p.line_number} in {p.function_name}()")
        print(f"  Exception: {p.exception_type}")
        print(f"  Context: {p.code_context[:100]}...")
        print()

    print("\n" + "=" * 60)
    print("SUMMARY FOR AUDIT_2.md COMPLIANCE")
    print("=" * 60)

    total_violations = len(violations)
    print(f"TOTAL VIOLATIONS TO FIX: {total_violations}")

    if total_violations > 0:
        print("❌ AUDIT_2.md COMPLIANCE: FAILED")
        print("   Must fix ALL violations to achieve ZERO technical debt")
    else:
        print("✅ AUDIT_2.md COMPLIANCE: PASSED")
        print("   ZERO technical debt achieved!")

    return violations, needs_review


if __name__ == "__main__":
    violations, needs_review = main()
