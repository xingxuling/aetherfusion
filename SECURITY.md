# Security Policy

## Reporting a Vulnerability

**Do not open a public issue with sensitive security details.**

Instead, use one of these channels:

- **GitHub Private Vulnerability Reporting**: Use the Security Advisory tab on the repository
- **Direct contact**: Reach out to the maintainers through the repository's security contacts

We aim to acknowledge reports within 72 hours and provide an initial assessment within 5 business days.

## Security Focus Areas

AetherFusion operates on local filesystems and manipulates source code. The following areas require particular scrutiny:

### Path Traversal

AetherFusion reads from and writes to user-specified directories. All path handling must prevent traversal outside the intended source and target project trees.

### Accidental Overwrites

Apply operations are restricted to `add_file` only — never modify or delete existing target files. Any expansion of apply capabilities must maintain this safety invariant.

### Sensitive Information Leakage

Diagnostic artifacts (fusion reports, repair plans, verify results) may contain file paths, dependency information, and code snippets. These must never be written outside the user-specified reports directory.

### Dangerous Command Execution

Verify mode runs whitelisted commands only. The whitelist must be conservative and clearly documented. No arbitrary command execution.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.1   | Yes       |
| 1.0.0   | Yes       |
| < 1.0.0 | No        |
