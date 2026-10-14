#!/usr/bin/env python3
"""Portable installer, available even when only the skill was downloaded."""
import sys

sys.dont_write_bytecode = True
from collablib.installer import main

if __name__ == "__main__":
    raise SystemExit(main())
