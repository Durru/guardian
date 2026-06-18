"""Shared test base class for isolated DB paths."""
import shutil
import tempfile
import unittest
from pathlib import Path


class IsolatedTest(unittest.TestCase):
    """Test class that isolates guardian_shared MEMORY_DIR/BACKEND_DIR per class."""

    @classmethod
    def setUpClass(cls):
        import guardian_shared as _shared
        cls._tmpdir = Path(tempfile.mkdtemp(prefix="guardian-test-"))
        cls._orig_mem = _shared.MEMORY_DIR
        cls._orig_backend = _shared.BACKEND_DIR
        _shared.MEMORY_DIR = cls._tmpdir
        _shared.BACKEND_DIR = cls._tmpdir
        _shared.project_dir("_guardian_base")

    @classmethod
    def tearDownClass(cls):
        import guardian_shared as _shared
        _shared.MEMORY_DIR = cls._orig_mem
        _shared.BACKEND_DIR = cls._orig_backend
        shutil.rmtree(cls._tmpdir, ignore_errors=True)
