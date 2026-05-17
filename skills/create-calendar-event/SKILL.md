---
name: create-calendar-event
description: Create a calendar event by generating an ICS file and opening it in the default calendar application. Use when the user wants to schedule a meeting, appointment, or reminder.
compatibility: Requires Python 3.10+. A default calendar application must be configured on the host system.
---

# create-calendar-event

Generates a standards-compliant `.ics` (iCalendar) file for a given event and
opens it with the OS default calendar app (Windows Calendar, macOS Calendar,
GNOME Calendar, etc.).  Accepts ISO-format datetimes.

## Usage

Call `create_calendar_event(title, start, end, description="", location="")`.

Datetime format: `"2025-06-15T14:00:00"`.

## Implementation

Logic lives in `scripts/create_calendar_event.py`.
