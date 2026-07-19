#!/usr/bin/env python3
"""Compatibility entrypoint for repository pytest execution."""

import os
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Run the configured repository suite independent of the caller's directory."""
    os.chdir(REPOSITORY_ROOT)
    arguments = sys.argv[1:] or ["-q"]
    return pytest.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
