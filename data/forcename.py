# data/forcenames.py
from data.db import get_connection

def get_forced_nickname(guild_id: int, user_id: int):
    """Returns {'original': str, 'forced': str} or None"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT original_name, forced_name FROM forced_nicknames WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        ).fetchone()
    if row:
        return {"original": row[0], "forced": row[1]}
    return None

def set_forced_nickname(guild_id: int, user_id: int, original: str, forced: str):
    """Store a forced nickname"""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO forced_nicknames (guild_id, user_id, original_name, forced_name) VALUES (?, ?, ?, ?)",
            (str(guild_id), str(user_id), original, forced)
        )

def remove_forced_nickname(guild_id: int, user_id: int) -> bool:
    """Remove forced nickname. Returns True if existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM forced_nicknames WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
    return cursor.rowcount > 0

def get_all_forced_in_guild(guild_id: int):
    """Returns list of (user_id, original, forced) tuples"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, original_name, forced_name FROM forced_nicknames WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchall()
    return [(int(row[0]), row[1], row[2]) for row in rows]