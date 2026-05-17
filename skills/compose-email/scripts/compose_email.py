"""Email composition skill — drafts mail via OS mailto: handler or SMTP."""

from __future__ import annotations

import platform
import subprocess
import urllib.parse


async def compose_email(
    to: str,
    subject: str,
    body: str,
) -> str:
    """Open the default mail client with a pre-filled draft email.

    This uses the OS mailto: protocol handler so no credentials are needed.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.
    """
    params = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    mailto_url = f"mailto:{urllib.parse.quote(to)}?{params}"

    system = platform.system()
    try:
        if system == "Windows":
            # os.startfile is Windows-only
            import os
            os.startfile(mailto_url)
        elif system == "Darwin":
            subprocess.Popen(["open", mailto_url])
        else:
            subprocess.Popen(["xdg-open", mailto_url])
        return f"Opened default mail client with draft to {to}."
    except Exception as exc:
        return f"Failed to open mail client: {exc}"
