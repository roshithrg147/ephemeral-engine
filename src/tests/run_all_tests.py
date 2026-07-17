#!/usr/bin/env python3
"""Compatibility entrypoint for repository pytest execution."""

import sys

import pytest


def main() -> int:
    return pytest.main(sys.argv[1:] or ["-q"])


if __name__ == "__main__":
    raise SystemExit(main())
