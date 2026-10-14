"""Validate the distributable Agent Skills layout and installed execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid


REPOSITORY = Path(__file__).resolve().parents[1]
SKILL = REPOSITORY / "skills" / "collab"


class SkillPackagingTests(unittest.TestCase):
    def test_required_metadata_and_portable_script_reference(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "SKILL.md requires YAML frontmatter")
        parts = text.split("---", 2)
        self.assertEqual(len(parts), 3)
        frontmatter, instructions = parts[1:]
        name = re.search(r"^name:\s*['\"]?([a-z0-9-]+)['\"]?\s*$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(name)
        self.assertEqual(name.group(1), SKILL.name)
        self.assertLessEqual(len(name.group(1)), 64)
        description = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(description, "A nonempty activation description is required")
        self.assertIn("scripts/collab.py", instructions)
        self.assertTrue((SKILL / "scripts" / "collab.py").is_file())
        self.assertNotRegex(text, r"(?i)[A-Z]:\\Users\\", "Skill must not embed a developer-specific path")
        self.assertLessEqual(len(text.splitlines()), 500, "Use progressive disclosure for lengthy detail")

    def test_copied_skill_runs_without_source_repository(self):
        with tempfile.TemporaryDirectory(prefix="collab-installed-") as directory:
            temporary = Path(directory)
            installed = temporary / "agent skills" / "collab"
            shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            project = temporary / "unrelated user project"
            project.mkdir()
            payload = temporary / "join.json"
            payload.write_text(json.dumps({
                "name": "Installed copy", "platform": "packaging-test",
                "session_id": str(uuid.uuid4()), "objective": "Validate portable installation",
            }), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(installed / "scripts" / "collab.py"),
                 "--root", str(project), "start", "--input", str(payload)],
                cwd=project, capture_output=True, text=True, encoding="utf-8",
                env=dict(os.environ, PYTHONUTF8="1", PYTHONPATH=""), timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["ok"])
            self.assertTrue((project / ".collab" / "GROUP_CHAT.jsonl").is_file())
            self.assertFalse((installed / ".collab").exists())


if __name__ == "__main__":
    unittest.main()
