# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes. We do not backport patches to older releases.

| Version | Supported |
|---|---|
| `main` (latest) | :white_check_mark: |
| Older releases | :x: |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.** Doing so could expose users before a fix is available.

Instead, report vulnerabilities through **GitHub's private security advisory** mechanism:

1. Go to the [Security tab](https://github.com/scarecr0w12/AzerothPanel/security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the form with as much detail as possible.

If you prefer e-mail, you can reach the maintainer at the address listed on their [GitHub profile](https://github.com/scarecr0w12).

---

## What to Include in Your Report

To help us triage and fix the issue quickly, please provide:

- **Description** – a clear summary of the vulnerability.
- **Impact** – what an attacker can achieve (e.g., unauthenticated RCE, SQL injection, JWT bypass).
- **Steps to reproduce** – a minimal reproduction case, including any exploit code or PoC.
- **Affected component** – which file(s), endpoint(s), or feature(s) are vulnerable.
- **Suggested fix** (optional) – if you have a patch or idea for remediation.

---

## Response Timeline

| Step | Target time |
|---|---|
| Acknowledgement of report | Within **48 hours** |
| Initial triage and severity assessment | Within **5 business days** |
| Fix or workaround published | Depends on severity (see below) |

| Severity | Fix target |
|---|---|
| Critical / High | Within **7 days** |
| Medium | Within **30 days** |
| Low / Informational | Best effort |

---

## Scope

This policy covers the AzerothPanel application code — the FastAPI backend, React frontend, host daemon (`ac_host_daemon.py`), and Docker configuration.

It does **not** cover:
- AzerothCore itself (report to the [AzerothCore project](https://github.com/azerothcore/azerothcore-wotlk/security/advisories/new)).
- Third-party dependencies — report vulnerabilities in dependencies to their respective maintainers; please also open a non-sensitive issue here so we can update the dependency.
- Vulnerabilities that require physical access to the host machine.

---

## Disclosure Policy

Once a fix is released, we will:

1. Publish a [GitHub Security Advisory](https://github.com/scarecr0w12/AzerothPanel/security/advisories).
2. Credit the reporter (unless they prefer to remain anonymous).
3. Tag a new release and update the `CHANGELOG.md`.

We follow a coordinated disclosure approach and ask reporters to respect a **90-day embargo** after the fix is available before publishing their own write-up.
