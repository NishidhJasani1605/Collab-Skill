# COLLAB readiness and validation report

Date: 2026-10-14 (Asia/Kolkata).
Scope: current local changes based on commit `9c53490`, recorded as Unreleased in CHANGELOG.md.
Package version remains `1.0.0-beta.1`; no release, tag, or remote publication is implied.

## Observed verification

| Environment | Command | Result |
| --- | --- | --- |
| Windows, Python 3.13.5 | `python -m unittest discover -s tests -v` | 70 tests, 69 passed, 1 skipped, 0 failures; 105.362 seconds |
| Ubuntu via WSL, Python 3.12.3 | `python3 -m unittest discover -s tests -v` | 70 tests, 69 passed, 1 skipped, 0 failures; 114.711 seconds |
| Windows, Python 3.11.14 | Lifecycle test module | 15 passed; 15.082 seconds |
| Windows, Python 3.13.5 | `python install.py --verify-only --json` | Complete package, Python syntax, relative references, and installed helper startup verified |
| Windows, Python 3.13.5 | `python examples/two_agents.py` | Independent-process A → B → A communication verified in a temporary project |
| Worktree | `git diff --check` and local documentation link inspection | No whitespace errors or missing local file targets |

The Windows skip requires unavailable symlink privileges; Windows junction protection passed. The Linux skip is the Windows-only junction test; Linux symlink protection passed. Linux test projects and simulated profiles were created in Linux temporary directories, independently from Windows runtime state.

## Requirements and evidence

| Requirement | Authoritative implementation and behavioral evidence |
| --- | --- |
| Installation creates no project COLLAB folders | All three entry points delegate to `collablib/installer.py`, default to global scope; `test_every_entrypoint_installs_globally_and_only_start_creates_runtime` checks an empty project after every installer and package verification. |
| Runtime appears only after collaboration starts | `execute` allows Store creation only for `start`; `read`, `status`, `check`, `send`, and `finalize` return NOT_INITIALIZED without creating directories. The same lifecycle test exercises these commands before activation. |
| One shared coordination folder | Two independent installed helpers join the same task; the lifecycle test asserts that the project's only new top-level folder is `.collab`. Chat, checkpoints, findings, reviews, decisions, logs, and edit staging are contained there. |
| Explicit activation | SKILL.md excludes installation/explanation/maintenance from activation. Codex policy disables implicit invocation; Claude/Cursor/Kimi frontmatter and OpenCode metadata supply the documented equivalent. Actual YAML values were parsed and checked. |
| Complete portable installation and Python prerequisites | Installer and package tests verify required files, helper startup, source-independent execution, missing/unsupported Python, path spaces, and all supported simulated host destinations. |
| Safe updates and removal | Lifecycle tests verify failed-stage preservation, failed-publication rollback without retained backups, unchanged identical copies, legacy upgrades without manifests, linked-path refusal, recursive-path refusal, invalid-plan rejection, and preservation of unrelated files and runtime history. |
| Concurrent installation | Three independent installer processes produce one complete working installation under an OS lock. |
| Coordination reliability | Process integration tests exercise task joining, messages, assignment ownership, dependencies, help, reviews, approval, and guarded finalization. Storage tests include 100 simultaneous submissions, 120 messages from 12 processes, OS lock release, and every defined crash-recovery boundary. |
| Completion integrity | Security/integration tests reject impersonation, absent or altered check logs, stale revisions, changed project files, observer approval, missing independent reviews, and unmet checks or artifacts. |
| Bounded check execution | Check tests drain 3 MB of output while retaining a bounded prefix, record failures and missing commands, terminate a timed-out command, and remove internal tokens/fault-injection variables from subprocess environments. |
| Contained project-edit staging | The security regression test inspects the temporary file location, simulates replacement failure, confirms the original file survives, then verifies successful replacement and staging cleanup. |
| Consistent documentation and release checks | README, INSTALL.md, installation/compatibility guides, references, and changelog describe the same lifecycle. CI runs package verification, the full dependency-free suite, and simulation on Windows/Linux/macOS with Python 3.10–3.14. |

## Defects corrected

- Removed divergent installer implementations and project-level default instructions.
- Prevented status/verification from initializing collaboration; added explicit invocation configuration.
- Corrected Antigravity App/IDE and CLI user skill paths.
- Prioritized active-host evidence over unrelated installed-host directories and avoided an extra universal copy during auto installation.
- Verified staged updates before publication, serialized mutations, added rollback, preserved legacy installations, and refused unrecognized or linked destinations.
- Stopped identical reinstalls from rewriting the installed package.
- Made invalid arguments and ordinary installation failures return structured JSON when requested.
- Bounded captured check output before persistence and rejected stale revisions before executing checks.
- Removed COLLAB session credentials from validation subprocess environments.
- Moved edit staging into `.collab/tmp` and refused atomic writes across filesystem boundaries.
- Corrected outdated test counts, uninstall examples, activation syntax, and the review-reference anchor.

## Readiness boundaries

The supported local collaboration runtime and clean-project installation lifecycle passed the observed checks. This is evidence for the documented cooperative local-filesystem design, not a guarantee that arbitrary workloads or every commercial host UI have been exercised.

- Full local suites were observed on Windows/Python 3.13 and Linux/Python 3.12; the lifecycle suite also ran on Windows/Python 3.11. The configured remote CI matrix, macOS, and Python 3.10/3.14 were not executed in this session.
- Live discovery and manual command activation in every named IDE were not automated. Paths and invocation policies follow the vendor documentation linked in Compatibility.md.
- The bundled skill-creator quick validator rejects `compatibility` and `disable-model-invocation` because its allowlist omits those documented fields. This failure is recorded; actual YAML parsing, current vendor documentation, and the repository's package verifier were used to assess the package.
- Direct Python invocation cannot prove what a user typed into a host; explicit-only behavior also depends on that host honoring its policy or skill instructions.
- Same-user processes are cooperating peers, not hostile tenants. Direct OS access can bypass this protocol. Network/cloud-sync state and mixed native Windows/WSL access to one runtime are unsupported.
- Authoritative history grows with bounded local tasks and is read under a single lock. There is no background daemon, automatic host wake-up, or private IDE-history capture.
- Update publication is transactional per destination with ordinary-failure rollback; power loss between renames requires recovery from the retained staging copy or backup.
- Check commands must be finite. Deliberately detached descendants and Windows descendants whose parent already exited are not guaranteed to be terminated.
- Existing project-local host folders are preserved; users should remove obsolete COLLAB copies specifically rather than delete whole host directories.
