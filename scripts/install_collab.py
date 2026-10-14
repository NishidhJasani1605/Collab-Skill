#!/usr/bin/env python3
"""Repository entry point; the distributable skill owns the installer."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts"))
from collablib import installer

main = installer.main
if __name__ == "__main__":
    raise SystemExit(main())
else:
    sys.modules[__name__] = installer
