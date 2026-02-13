from data.db import get_connection


def get_timezone(user_id: int) -> str | None:
    """Return the timezone string for a user, or None if not set."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT timezone FROM timezones WHERE user_id = ?",
            (str(user_id),)
        ).fetchone()
    return row[0] if row else None


def set_timezone(user_id: int, timezone: str):
    """Set or update a user's timezone."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO timezones (user_id, timezone) VALUES (?, ?)",
            (str(user_id), timezone)
        )