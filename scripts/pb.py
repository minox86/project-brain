#!/usr/bin/env python3
"""Entry point of the pb toolkit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pb_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
