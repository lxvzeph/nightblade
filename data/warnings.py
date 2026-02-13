import time
from data.db import get_connection


def add_warning(guild_id: int, user_id: int, mod_id: int, reason: str) -> int:
    """
    Insert a warning and return the new total warning count for that member.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO warnings (guild_id, user_id, mod_id, reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (str(guild_id), str(user_id), str(mod_id), reason, int(time.time())))

        count = conn.execute("""
            SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?
        """, (str(guild_id), str(user_id))).fetchone()[0]

    return count


def get_warnings(guild_id: int, user_id: int) -> list[dict]:
    """Return all warnings for a member, sorted oldest first."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT mod_id, reason, timestamp
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY timestamp ASC
        """, (str(guild_id), str(user_id))).fetchall()

    return [{"mod": int(row[0]), "reason": row[1], "timestamp": row[2]} for row in rows]

def remove_warning(guild_id: int, user_id: int, warning_number: int) -> bool:
    """
    Delete a single warning by its 1-based position (oldest = 1).
    Returns True if a row was deleted, False if the number is out of range.
    """
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY timestamp ASC
            LIMIT 1 OFFSET ?
        """, (str(guild_id), str(user_id), warning_number - 1)).fetchone()

        if not row:
            return False

        conn.execute("DELETE FROM warnings WHERE id = ?", (row[0],))

    return True

def clear_warnings(guild_id: int, user_id: int) -> int:
    """Delete all warnings for a member. Returns the number of rows deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
    return cursor.rowcount