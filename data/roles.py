from data.db import get_connection


def backup_member_roles(guild_id: int, user_id: int, role_ids: list[int]):
    """
    Save a member's role IDs, replacing any existing backup.
    Stores an empty backup correctly (member row exists, no role rows).
    """
    gid = str(guild_id)
    uid = str(user_id)

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO role_backup_members (guild_id, user_id) VALUES (?, ?)",
            (gid, uid)
        )
        conn.execute(
            "DELETE FROM role_backup WHERE guild_id = ? AND user_id = ?",
            (gid, uid)
        )
        for role_id in role_ids:
            conn.execute(
                "INSERT OR IGNORE INTO role_backup (guild_id, user_id, role_id) VALUES (?, ?, ?)",
                (gid, uid, str(role_id))
            )


def get_member_role_backup(guild_id: int, user_id: int) -> list[int] | None:
    """
    Return a list of backed-up role IDs, or None if no backup exists at all.
    Returns an empty list if the member had no roles when backed up.
    """
    gid = str(guild_id)
    uid = str(user_id)

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM role_backup_members WHERE guild_id = ? AND user_id = ?",
            (gid, uid)
        ).fetchone()

        if not exists:
            return None

        rows = conn.execute(
            "SELECT role_id FROM role_backup WHERE guild_id = ? AND user_id = ?",
            (gid, uid)
        ).fetchall()

    return [int(row[0]) for row in rows]


def clear_member_role_backup(guild_id: int, user_id: int) -> bool:
    """
    Delete a member's backup entirely.
    Returns True if a backup existed and was deleted, False if nothing was found.
    """
    gid = str(guild_id)
    uid = str(user_id)

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM role_backup WHERE guild_id = ? AND user_id = ?",
            (gid, uid)
        )
        cursor = conn.execute(
            "DELETE FROM role_backup_members WHERE guild_id = ? AND user_id = ?",
            (gid, uid)
        )

    return cursor.rowcount > 0