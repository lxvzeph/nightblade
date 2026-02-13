from data.db import get_connection


def get_autorole(guild_id: int) -> int | None:
    """Return the autorole role_id for a guild, or None if not set."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role_id FROM autoroles WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()
    return int(row[0]) if row else None


def set_autorole(guild_id: int, role_id: int):
    """Set or replace the autorole for a guild."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO autoroles (guild_id, role_id) VALUES (?, ?)",
            (str(guild_id), str(role_id))
        )


def delete_autorole(guild_id: int) -> bool:
    """Remove a guild's autorole. Returns True if one existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM autoroles WHERE guild_id = ?",
            (str(guild_id),)
        )
    return cursor.rowcount > 0