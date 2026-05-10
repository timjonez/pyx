"""Runtime support for pyx - HTML string generation helpers."""

import html


class SafeString(str):
    """A string that should not be HTML-escaped."""
    pass


def _escape(value: object) -> str:
    """Escape a value for safe HTML insertion."""
    if isinstance(value, SafeString):
        return str(value)
    return html.escape(str(value))


def safe(value: object) -> SafeString:
    """Mark a string as safe HTML - it will not be escaped."""
    return SafeString(str(value))
