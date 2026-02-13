import json
from data.db import get_connection


def get_sticky(channel_id: int) -> dict | None:
    """Return sticky data for a channel, or None if not set."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT content, embeds, attachments, message_id FROM sticky_messages WHERE channel_id = ?",
            (str(channel_id),)
        ).fetchone()
    if not row:
        return None
    return {
        "content":     row[0],
        "embeds":      json.loads(row[1]) if row[1] else [],
        "attachments": json.loads(row[2]) if row[2] else [],
        "message_id":  int(row[3]),
    }


def set_sticky(channel_id: int, content, embeds: list, attachments: list, message_id: int):
    """Insert or replace a sticky message entry."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO sticky_messages (channel_id, content, embeds, attachments, message_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(channel_id),
            content,
            json.dumps(embeds) if embeds else None,
            json.dumps(attachments) if attachments else None,
            str(message_id),
        ))


def update_sticky_message_id(channel_id: int, message_id: int):
    """Update just the message_id after re-posting the sticky."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE sticky_messages SET message_id = ? WHERE channel_id = ?",
            (str(message_id), str(channel_id))
        )


def delete_sticky(channel_id: int) -> bool:
    """Remove a sticky entry. Returns True if one existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM sticky_messages WHERE channel_id = ?",
            (str(channel_id),)
        )
    return cursor.rowcount > 0


def get_all_stickies() -> dict:
    """Load all sticky entries on cog startup."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT channel_id, content, embeds, attachments, message_id FROM sticky_messages"
        ).fetchall()
    result = {}
    for row in rows:
        result[row[0]] = {
            "content":     row[1],
            "embeds":      json.loads(row[2]) if row[2] else [],
            "attachments": json.loads(row[3]) if row[3] else [],
            "message_id":  int(row[4]),
        }
    return result