from data.db import get_connection


def get_jail_config(guild_id: int) -> dict | None:
    """Return {role_id, channel_id} for a guild, or None if not configured."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role_id, channel_id FROM jail_config WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()
    if not row:
        return None
    return {"role_id": int(row[0]), "channel_id": int(row[1])}


def set_jail_config(guild_id: int, role_id: int, channel_id: int):
    """Set or replace the jail config for a guild."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO jail_config (guild_id, role_id, channel_id) VALUES (?, ?, ?)",
            (str(guild_id), str(role_id), str(channel_id))
        )


def delete_jail_config(guild_id: int) -> bool:
    """Remove a guild's jail config. Returns True if one existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM jail_config WHERE guild_id = ?",
            (str(guild_id),)
        )
    return cursor.rowcount > 0