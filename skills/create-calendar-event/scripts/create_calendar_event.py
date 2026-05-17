"""Calendar event creation — opens the default calendar via OS protocol handler."""

from __future__ import annotations

import platform
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


async def create_calendar_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create a calendar event by generating an .ics file and opening it with the default calendar app.

    Args:
        title: Event title / summary.
        start: Start datetime in ISO format (e.g. '2025-01-15T10:00:00').
        end: End datetime in ISO format (e.g. '2025-01-15T11:00:00').
        description: Optional event description.
        location: Optional event location.
    """
    try:
        dt_start = datetime.fromisoformat(start)
        dt_end = datetime.fromisoformat(end)
    except ValueError as exc:
        return f"Invalid datetime format: {exc}. Use ISO format like '2025-01-15T10:00:00'."

    fmt = "%Y%m%dT%H%M%S"
    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//uZephyr//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART:{dt_start.strftime(fmt)}\r\n"
        f"DTEND:{dt_end.strftime(fmt)}\r\n"
        f"SUMMARY:{title}\r\n"
        f"DESCRIPTION:{description}\r\n"
        f"LOCATION:{location}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    tmp_dir = Path(tempfile.mkdtemp())
    ics_path = tmp_dir / "event.ics"
    ics_path.write_text(ics_content, encoding="utf-8")

    system = platform.system()
    try:
        if system == "Windows":
            import os
            os.startfile(str(ics_path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(ics_path)])
        else:
            subprocess.Popen(["xdg-open", str(ics_path)])
        return f"Calendar event '{title}' created and opened in default calendar app."
    except Exception as exc:
        return f"Failed to open calendar event: {exc}. ICS file saved at {ics_path}"
