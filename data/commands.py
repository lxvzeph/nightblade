from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────────────
# DISABLED COMMANDS
# channel_id = "0" means server-wide, otherwise it's a specific channel ID
# ─────────────────────────────────────────────────────────────────────────────

def get_disabled_commands(guild_id: int) -> list[dict]:
    """Return list of {command_name, channel_id} dicts for a guild."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT command_name, channel_id FROM disabled_commands WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchall()
    return [{"command_name": row[0], "channel_id": row[1]} for row in rows]


def disable_command(guild_id: int, command_name: str, channel_id: int = 0):
    """
    Disable a command. channel_id=0 means server-wide.
    Specific channel disables stack on top of server-wide ones.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO disabled_commands (guild_id, command_name, channel_id) VALUES (?, ?, ?)",
            (str(guild_id), command_name, str(channel_id))
        )


def enable_command(guild_id: int, command_name: str, channel_id: int = 0) -> bool:
    """
    Re-enable a command. channel_id=0 removes the server-wide disable.
    Returns True if the entry existed and was removed.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM disabled_commands WHERE guild_id = ? AND command_name = ? AND channel_id = ?",
            (str(guild_id), command_name, str(channel_id))
        )
    return cursor.rowcount > 0


def is_command_disabled(guild_id: int, command_name: str, channel_id: int = 0) -> bool:
    """
    Returns True if the command is disabled server-wide OR in the given channel.
    Pass channel_id=0 to only check server-wide.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM disabled_commands
            WHERE guild_id = ? AND command_name = ?
            AND (channel_id = '0' OR channel_id = ?)
            """,
            (str(guild_id), command_name, str(channel_id))
        ).fetchone()
    return row is not None


def is_command_disabled_serverwide(guild_id: int, command_name: str) -> bool:
    """Returns True only if the command is disabled server-wide (channel_id = '0')."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM disabled_commands WHERE guild_id = ? AND command_name = ? AND channel_id = '0'",
            (str(guild_id), command_name)
        ).fetchone()
    return row is not None


def is_command_disabled_in_channel(guild_id: int, command_name: str, channel_id: int) -> bool:
    """Returns True only if the command is disabled in a specific channel."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM disabled_commands WHERE guild_id = ? AND command_name = ? AND channel_id = ?",
            (str(guild_id), command_name, str(channel_id))
        ).fetchone()
    return row is not None


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND RESTRICTIONS (allowlist)
# type is one of: "role", "channel", "user"
# If any list is non-empty, the invoker must satisfy that list to use the command.
# ─────────────────────────────────────────────────────────────────────────────

def get_restrictions(guild_id: int, command_name: str) -> dict:
    """
    Return {roles: [...], channels: [...], users: [...]} for a command.
    All values are ints. Empty lists mean no restriction for that type.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT type, value_id FROM command_restrictions WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        ).fetchall()
    result = {"roles": [], "channels": [], "users": []}
    for rtype, value_id in rows:
        key = rtype + "s"
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
    Add an allowlist entry. rtype must be "role", "channel", or "user".
    INSERT OR IGNORE so duplicates are silently skipped.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO command_restrictions (guild_id, command_name, type, value_id) VALUES (?, ?, ?, ?)",
            (str(guild_id), command_name, rtype, str(value_id))
        )


def remove_restriction(guild_id: int, command_name: str, rtype: str, value_id: int) -> bool:
    """Remove a specific allowlist entry. Returns True if it existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM command_restrictions WHERE guild_id = ? AND command_name = ? AND type = ? AND value_id = ?",
            (str(guild_id), command_name, rtype, str(value_id))
        )
    return cursor.rowcount > 0


def clear_command_restrictions(guild_id: int, command_name: str):
    """Remove all allowlist entries for a specific command."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM command_restrictions WHERE guild_id = ? AND command_name = ?",
            (str(guild_id), command_name)
        )