---
name: compose-email
description: Open the default mail client with a pre-filled draft email using the OS mailto protocol handler. Use when the user wants to compose or send an email.
compatibility: Requires Python 3.10+. A default mail client must be configured on the host system.
---

# compose-email

Opens the system default mail client (Outlook, Thunderbird, Apple Mail, etc.)
with `to`, `subject`, and `body` pre-filled via a `mailto:` URL.  No
credentials or SMTP configuration required.

## Usage

Call `compose_email(to, subject, body)`.

## Implementation

Logic lives in `scripts/compose_email.py`.
