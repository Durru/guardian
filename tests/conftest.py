"""Pytest config: reset Guardian caches between tests."""
import sys
import pytest


@pytest.fixture(autouse=True)
def reset_guardian_caches():
    if 'guardian_brain' in sys.modules:
        try:
            sys.modules['guardian_brain']._reset_conn_cache()
        except Exception:
            pass
    if 'guardian_shared' in sys.modules:
        try:
            sys.modules['guardian_shared']._BRANCH_HASH_CACHE = None
        except Exception:
            pass
    yield
