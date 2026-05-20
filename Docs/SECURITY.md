# Security Policy

## Supported Versions

Currently, the `main` branch of μZephyr is actively maintained and receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

As a local-first AI orchestration layer designed for private, on-device workflows, the privacy and security of your data are our highest priorities.

If you discover a security vulnerability within μZephyr, please do not disclose it publicly until it has been addressed. 

To report a vulnerability:
1. Contact the repository owner directly or create a private GitHub Security Advisory.
2. Provide details on how to reproduce the issue and the potential impact.

### Areas of Critical Concern
We are especially interested in reports regarding:
- Unauthorized access to `zephyr.db` or `vector_store/` contents.
- Escaping the **Docker-backed sandbox**.
- Potential path traversal or unauthorized file system operations by local agents.

We aim to address critical security vulnerabilities rapidly.
