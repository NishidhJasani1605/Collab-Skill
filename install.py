#!/usr/bin/env python3
"""
Root entrypoint for installing the COLLAB skill.
Delegates directly to skills/collab/scripts/install.py.
"""

from __future__ import annotations

import pathlib
import sys

# Ensure skills/collab/scripts is importable
repo_root = pathlib.Path(__file__).resolve().parent
installer_module_path = repo_root / "skills" / "collab" / "scripts" / "install.py"

if not installer_module_path.exists():
    sys.stderr.write(f"Error: installer script not found at {installer_module_path}\n")
    sys.exit(1)

import importlib.util

spec = importlib.util.spec_from_file_location("collab_installer", str(installer_module_path))
if spec is None or spec.loader is None:
    sys.stderr.write("Error: could not load installer spec\n")
    sys.exit(1)

installer_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer_mod)

if __name__ == "__main__":
    sys.exit(installer_mod.main())
