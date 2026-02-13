from data.db import get_connection

def get_prefix_for_guild(guild_id: int) -> str:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT prefix FROM prefixes WHERE guild_id = ?",
            (str(guild_id),)
        )
        row = cur.fetchone()
        return row[0] if row else ";"


def set_prefix_for_guild(guild_id: int, prefix: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO prefixes (guild_id, prefix)
            VALUES (?, ?)
            """,
            (str(guild_id), prefix)
        )


def delete_prefix_for_guild(guild_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM prefixes WHERE guild_id = ?",
            (str(guild_id),)
        )
