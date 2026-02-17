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

def get_all_timezones_in_guild(user_ids: list[int]) -> dict[int, str]:
    """Return {user_id: timezone} for all provided user_ids that have a timezone set."""
    if not user_ids:
        return {}
    placeholders = ",".join("?" * len(user_ids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT user_id, timezone FROM timezones WHERE user_id IN ({placeholders})",
            [str(uid) for uid in user_ids]
        ).fetchall()
    return {int(row[0]): row[1] for row in rows}