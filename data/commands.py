from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────────────
# DISABLED COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

def get_disabled_commands(guild_id: int) -> list[str]:
    """Return list of disabled command names for a guild."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT command_name FROM disabled_commands WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchall()
    return [row[0] for row in rows]


def disable_command(guild_id: int, command_name: str):
    """Mark a command as disabled in a guild."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO disabled_commands (guild_id, command_name) VALUES (?, ?)",
            (str(guild_id), command_name)
        )


def enable_command(guild_id: int, command_name: str) -> bool:
    """Re-enable a command. Returns True if it was disabled."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM disabled_commands WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        )
    return cursor.rowcount > 0


def is_command_disabled(guild_id: int, command_name: str) -> bool:
    """Return True if the command is disabled in this guild."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM disabled_commands WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        ).fetchone()
    return row is not None


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND RESTRICTIONS
# type is one of: "role", "channel", "user"
# ─────────────────────────────────────────────────────────────────────────────

def get_restrictions(guild_id: int, command_name: str) -> dict:
    """
    Return {roles: [...], channels: [...], users: [...]} for a command.
    All values are ints. Empty lists if no restrictions set.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT type, value_id FROM command_restrictions WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        ).fetchall()
    result = {"roles": [], "channels": [], "users": []}
    for rtype, value_id in rows:
        key = rtype + "s"  # "role" -> "roles" etc.
        if key in result:
            result[key].append(int(value_id))
    return result


def get_all_restrictions(guild_id: int) -> dict:
    """
    Return all restrictions for a guild as:
    {command_name: {roles: [...], channels: [...], users: [...]}}
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT command_name, type, value_id FROM command_restrictions WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchall()
    result = {}
    for cmd, rtype, value_id in rows:
        if cmd not in result:
            result[cmd] = {"roles": [], "channels": [], "users": []}
        key = rtype + "s"
        if key in result[cmd]:
            result[cmd][key].append(int(value_id))
    return result


def add_restriction(guild_id: int, command_name: str, rtype: str, value_id: int):
    """
    Add a restriction. rtype must be "role", "channel", or "user".
    INSERT OR IGNORE so duplicates are silently skipped.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO command_restrictions (guild_id, command_name, type, value_id) VALUES (?, ?, ?, ?)",
            (str(guild_id), command_name, rtype, str(value_id))
        )


def remove_restriction(guild_id: int, command_name: str, rtype: str, value_id: int) -> bool:
    """Remove a specific restriction. Returns True if it existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM command_restrictions WHERE guild_id = ? AND command_name = ? AND type = ? AND value_id = ?",
            (str(guild_id), command_name, rtype, str(value_id))
        )
    return cursor.rowcount > 0


def clear_command_restrictions(guild_id: int, command_name: str):
    """Remove all restrictions for a specific command."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM command_restrictions WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        )