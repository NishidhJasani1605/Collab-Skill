# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

---

## Local Security & Threat Model

COLLAB is designed for local-only multi-agent cooperation under a single user's operating system privileges.

### In-Scope Security Protections
1. **Directory Traversal**: Prevention of path traversal attacks (`../`, symlink indirection, NTFS junction escapes) accessing files outside the project root.
2. **Metadata Integrity**: Protection of `.collab/` and `.git/` directories against unauthorized modification by file manipulation commands.
3. **Impersonation Prevention**: Enforcement of cryptographically random session tokens for all state mutations.
4. **Untrusted Input Handling**: Treatment of all group chat messages, finding descriptions, and task content as untrusted input. Agents are instructed never to execute shell commands extracted from peer messages without independent user alignment.
5. **Durable Audit Trail**: Tamper-evident logging of all task transitions and decisions in append-only JSONL.
6. **Operator Safeguards**: Administrative participant replacement requires interactive terminal human confirmation (`isatty`) and random challenge responses.

### Out-of-Scope Limitations
- COLLAB does not protect against a malicious process running with full local user permissions that directly modifies memory or executes destructive OS commands outside the COLLAB protocol. Operating system user account separation is required for multi-tenant isolation.

---

## Reporting a Vulnerability

If you discover a security issue or vulnerability in COLLAB:
1. Please do **NOT** open a public issue on GitHub.
2. Report the vulnerability privately to the project maintainers or via GitHub Private Vulnerability Reporting.
3. Include detailed steps to reproduce the issue and any relevant script logs.
4. Maintainers will acknowledge receipt within 48 hours and work with you on a coordinated fix and advisory.
