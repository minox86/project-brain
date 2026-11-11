#!/usr/bin/env python3
"""Entry point of the pb toolkit."""
import os
import sys

# No __pycache__ next to the vendored toolkit: CI would see it as a stale generated file, the routine would
# commit it.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pb_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
