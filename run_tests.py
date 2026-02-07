#!/usr/bin/env python3
"""
Simple test runner for scam tracker tests.
Can be run without pytest installed.
"""
import sys
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_tests():
    """Run all test modules"""
    test_dir = project_root / "tests"

    # Find all test files
    test_files = list(test_dir.glob("test_*.py"))

    if not test_files:
        print("No test files found in tests/")
        return 1

    print(f"Found {len(test_files)} test file(s)")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = []

    for test_file in test_files:
        print(f"\nRunning {test_file.name}...")
        print("-" * 60)

        # Import the test module
        module_name = test_file.stem
        try:
            # Dynamic import
            spec = __import__(f"tests.{module_name}", fromlist=[""])
            tests.run_module(spec, module_name, errors)
        except Exception as e:
            print(f"ERROR loading {test_file.name}: {e}")
            traceback.print_exc()
            errors.append((test_file.name, "LOAD_ERROR", str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Errors: {len(errors)}")

    if errors:
        print("\nFailed tests:")
        for name, kind, err in errors:
            print(f"  - {name}: {kind}")
            print(f"    {err}")

    return 1 if failed > 0 or errors else 0


if __name__ == "__main__":
    sys.exit(run_tests())
