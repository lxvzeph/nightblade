from data.db import get_connection


def get_license(guild_id: int) -> dict | None:
    """Return {key, activated} for a guild, or None if no entry exists."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT key, activated FROM licenses WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()
    if not row:
        return None
    return {"key": row[0], "activated": bool(row[1])}


def get_all_keys() -> set[str]:
    """Return all existing license keys — used to avoid duplicates on genkey."""
    with get_connection() as conn:
        rows = conn.execute("SELECT key FROM licenses").fetchall()
    return {row[0] for row in rows}


def create_license(guild_id: int, key: str):
    """Insert a new unactivated license for a guild."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO licenses (guild_id, key, activated) VALUES (?, ?, 0)",
            (str(guild_id), key)
        )


def set_activated(guild_id: int, activated: bool):
    """Set the activated flag for a guild's license."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE licenses SET activated = ? WHERE guild_id = ?",
            (1 if activated else 0, str(guild_id))
        )


def delete_license(guild_id: int) -> bool:
    """Delete a guild's license entirely. Returns True if one existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM licenses WHERE guild_id = ?",
            (str(guild_id),)
        )
    return cursor.rowcount > 0