from data.db import get_connection


def get_imute_role_id(guild_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role_id FROM imute_config WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()
        return int(row[0]) if row else None


def set_imute_role_id(guild_id: int, role_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO imute_config (guild_id, role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET role_id = excluded.role_id
            """,
            (str(guild_id), str(role_id))
        )

def delete_imute_role(guild_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM imute_config WHERE guild_id = ?",
            (str(guild_id),)
        )
        conn.commit()
