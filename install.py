#!/usr/bin/env python3
"""
Root entrypoint for installing the COLLAB skill.
Delegates directly to scripts/install_collab.py.
"""

from __future__ import annotations

import pathlib
import sys

sys.dont_write_bytecode = True

repo_root = pathlib.Path(__file__).resolve().parent
installer_script = repo_root / "scripts" / "install_collab.py"

if not installer_script.exists():
    sys.stderr.write(f"Error: installer script not found at {installer_script}\n")
    sys.exit(1)

import importlib.util

spec = importlib.util.spec_from_file_location("install_collab", str(installer_script))
if spec is None or spec.loader is None:
    sys.stderr.write("Error: could not load install_collab spec\n")
    sys.exit(1)

installer_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer_mod)

if __name__ == "__main__":
    sys.exit(installer_mod.main())
