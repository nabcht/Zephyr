# Security Policy

## Supported Versions

Currently, the `main` branch of μZephyr is the actively maintained line and receives security fixes.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

As a local-first AI orchestration layer designed for private, on-device workflows, the privacy and security of your data are our highest priorities.

If you discover a security vulnerability within μZephyr, please do not disclose it publicly until it has been addressed. 

To report a vulnerability:
1. Email nebil.chtourou@gmail.com directly.
2. Provide details on how to reproduce the issue and the potential impact.

### Areas of Critical Concern
We are especially interested in reports regarding:
- Unauthorized access to `zephyr.db` or `vector_store/` contents.
- Escaping the **Docker-backed sandbox**.
- Potential path traversal or unauthorized file system operations by local agents.
- Unsafe handling of session attachments under `temp_core/attachments`.
- MCP or subprocess configuration paths that could lead to unintended command execution.
- Incorrect behavior in `allow_sensitive_tools` or `REQUIRE_CONFIRMATION` enforcement.
- Exposure of the local-host backend to a wider network without appropriate external access controls.

We aim to address critical security vulnerabilities rapidly.
