import importlib.metadata
import sys
import pytest


def test_python_version():
    """Verify host Python runtime is version 3.12 or higher."""
    major, minor = sys.version_info[:2]
    assert (major, minor) >= (3, 12), f"Expected Python >= 3.12, got {major}.{minor}"


def test_core_dependencies_importable():
    """Verify all core native and pure Python dependencies import cleanly."""
    import fastapi
    import pydantic
    import sqlalchemy
    import demoparser2
    from demoparser2 import DemoParser
    import polars
    import numpy
    import zstandard
    import argon2
    import reportlab

    assert fastapi.__version__ is not None
    assert pydantic.__version__ is not None
    assert sqlalchemy.__version__ is not None
    # demoparser2 Rust-backed parser entrypoints and package metadata
    assert callable(DemoParser.parse_events)
    assert callable(DemoParser.parse_ticks)
    assert callable(DemoParser.parse_header)
    assert callable(DemoParser.parse_player_info)
    assert importlib.metadata.version("demoparser2") is not None
    assert polars.__version__ is not None
    assert numpy.__version__ is not None
    assert zstandard.__version__ is not None
    assert importlib.metadata.version("argon2-cffi") is not None
    assert reportlab.__version__ is not None


def test_backend_app_package():
    """Verify backend.app package is importable."""
    import backend.app

    assert backend.app is not None
