import time
from data.db import get_connection


def create_case(guild_id: int, user_id: int, case_type: str, reason: str | None, mod_id: int) -> int:
    """
    Insert a new case and return its guild-scoped case number.
    case_type: "ban"|"kick"|"timeout"|"jail"|"imute"|"rmute"
    """
    gid = str(guild_id)
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO case_counters (guild_id, case_counter) VALUES (?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET case_counter = case_counter + 1
        """, (gid,))

        case_num = conn.execute(
            "SELECT case_counter FROM case_counters WHERE guild_id = ?", (gid,)
        ).fetchone()[0]

        conn.execute("""
            INSERT INTO cases (guild_id, case_num, user_id, mod_id, type, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (gid, case_num, str(user_id), str(mod_id), case_type, reason, int(time.time())))

    return case_num


def get_case(guild_id: int, case_id: int) -> dict | None:
    """Return a single case as a dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT case_num, user_id, mod_id, type, reason, timestamp
            FROM cases WHERE guild_id = ? AND case_num = ?
        """, (str(guild_id), case_id)).fetchone()

    if not row:
        return None
    return {
        "case_num":  row[0],
        "user_id":   int(row[1]),
        "mod":       int(row[2]),
        "type":      row[3],
        "reason":    row[4],
        "timestamp": row[5],
    }


def get_cases_for_member(guild_id: int, user_id: int) -> list[tuple]:
    """Return [(case_num, case_dict), ...] sorted by case_num ascending."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT case_num, user_id, mod_id, type, reason, timestamp
            FROM cases WHERE guild_id = ? AND user_id = ?
            ORDER BY case_num ASC
        """, (str(guild_id), str(user_id))).fetchall()

    return [(row[0], {
        "case_num":  row[0],
        "user_id":   int(row[1]),
        "mod":       int(row[2]),
        "type":      row[3],
        "reason":    row[4],
        "timestamp": row[5],
    }) for row in rows]


def remove_case(guild_id: int, case_id: int) -> bool:
    """Delete a single case. Returns True if a row was deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM cases WHERE guild_id = ? AND case_num = ?",
            (str(guild_id), case_id)
        )
    return cursor.rowcount > 0


def clear_member_cases(guild_id: int, user_id: int) -> int:
    """Delete all cases for a member. Returns the number of rows deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM cases WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
    return cursor.rowcount