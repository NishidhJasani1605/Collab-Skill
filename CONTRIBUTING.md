# Contributing to COLLAB

Thank you for your interest in contributing to COLLAB! We welcome contributions from human developers and AI pair programmers alike.

---

## Development Workflow

### Prerequisites
- Python 3.10 or higher.
- Python unittest (built in); pytest is optional.
- Git.

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/NishidhJasani1605/Collab-Skill.git
   cd Collab-Skill
   ```
2. Verify the test suite:
   ```bash
   python -m unittest discover -s tests -v
   ```

---

## Coding Standards & Architectural Guidelines

1. **Zero External Runtime Dependencies**:
   - The runtime engine (`skills/collab/scripts/`) must rely exclusively on Python standard library modules (`os`, `sys`, `json`, `pathlib`, `fcntl`, `msvcrt`, `hashlib`, `secrets`, etc.).
   - Do not add external package dependencies to runtime code.
2. **Standard Library Naming Discipline**:
   - Never name scripts or modules with names that shadow Python standard library modules (e.g. `operator`, `io`, `typing`, `copy`).
3. **Cross-Platform Compatibility**:
   - All filesystem operations must work seamlessly on Windows (NT), Linux, and macOS.
   - Use `safe_project_path` and `fingerprint` for consistent file access and hashing.
4. **Guarded State Transitions**:
   - Any modification to task completion or participant states must be enforced by `collablib/engine.py` and committed through `collablib/storage.py` under lock.
5. **Progressive Disclosure**:
   - Keep `SKILL.md` concise (< 500 lines). Detailed command specifications and safety rules belong in `references/`.

---

## Running Tests

Run the full automated test suite before opening a pull request:

```bash
# Full test suite
python -m unittest discover -s tests -v

# Process integration tests
python -m unittest discover -s tests -p test_integration.py

# Storage & concurrency stress tests
python -m unittest discover -s tests -p test_storage.py

# Protocol security & finalization tests
python -m unittest discover -s tests -p test_engine_security.py

# Agent Skills packaging tests
python -m unittest discover -s tests -p test_skill.py
```

---

## Pull Request Guidelines

1. Ensure the full test suite and package verification pass.
2. If introducing new protocol events or states, update:
   - `docs/PROTOCOL.md`
   - `skills/collab/references/commands.md`
   - Corresponding test coverage in `tests/`.
3. Submit a clear, descriptive pull request detailing your changes, motivation, and verification steps.
