from datetime import datetime
from data.db import get_connection

def load_all_snipes() -> tuple[dict, dict, dict]:
    """
    Load all three snipe dicts from the DB.
    Returns (messages, reactions, edits) same shape as self.snipes etc.
    Keys are int channel IDs, values are lists of dicts.
    """
    messages  = {}
    reactions = {}
    edits     = {}

    with get_connection() as conn:
        for row in conn.execute("SELECT channel_id, author_id, author_name, author_avatar_url, content, attachments, time FROM snipes_messages").fetchall():
            cid = int(row[0])
            messages.setdefault(cid, []).append({
                "author_id":        int(row[1]),
                "author_name":      row[2],
                "author_avatar_url": row[3],
                "content":          row[4],
                "attachments":      [{"url": u} for u in row[5].split(",") if u] if row[5] else [],
                "time":             datetime.fromisoformat(row[6]),
            })

        for row in conn.execute("SELECT channel_id, user_id, user_name, user_avatar_url, emoji, message_id, message_url, time FROM snipes_reactions").fetchall():
            cid = int(row[0])
            reactions.setdefault(cid, []).append({
                "user_id":          int(row[1]),
                "user_name":        row[2],
                "user_avatar_url":  row[3],
                "emoji":            row[4],
                "message_id":       int(row[5]),
                "message_url":      row[6],
                "time":             datetime.fromisoformat(row[7]),
            })

        for row in conn.execute("SELECT channel_id, author_id, author_name, author_avatar_url, before_content, after_content, message_url, time FROM snipes_edits").fetchall():
            cid = int(row[0])
            edits.setdefault(cid, []).append({
                "author_id":        int(row[1]),
                "author_name":      row[2],
                "author_avatar_url": row[3],
                "before":           row[4],
                "after":            row[5],
                "message_url":      row[6],
                "time":             datetime.fromisoformat(row[7]),
            })

    return messages, reactions, edits


def save_message_snipe(channel_id: int, snipe: dict):
    """Insert a single message snipe row."""
    attachments_str = ",".join(a["url"] for a in snipe.get("attachments", []))
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO snipes_messages
                (channel_id, author_id, author_name, author_avatar_url, content, attachments, time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(channel_id),
            str(snipe["author_id"]),
            snipe["author_name"],
            snipe.get("author_avatar_url"),
            snipe.get("content"),
            attachments_str,
            snipe["time"].isoformat(),
        ))


def save_reaction_snipe(channel_id: int, snipe: dict):
    """Insert a single reaction snipe row."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO snipes_reactions
                (channel_id, user_id, user_name, user_avatar_url, emoji, message_id, message_url, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(channel_id),
            str(snipe["user_id"]),
            snipe["user_name"],
            snipe.get("user_avatar_url"),
            snipe["emoji"],
            str(snipe["message_id"]),
            snipe["message_url"],
            snipe["time"].isoformat(),
        ))


def save_edit_snipe(channel_id: int, snipe: dict):
    """Insert a single edit snipe row."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO snipes_edits
                (channel_id, author_id, author_name, author_avatar_url, before_content, after_content, message_url, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(channel_id),
            str(snipe["author_id"]),
            snipe["author_name"],
            snipe.get("author_avatar_url"),
            snipe.get("before"),
            snipe.get("after"),
            snipe["message_url"],
            snipe["time"].isoformat(),
        ))


def delete_message_snipe(channel_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM snipes_messages WHERE channel_id = ?",
            (str(channel_id),)
        )


def delete_reaction_snipe(channel_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM snipes_reactions WHERE channel_id = ?",
            (str(channel_id),)
        )


def delete_edit_snipe(channel_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM snipes_edits WHERE channel_id = ?",
        (str(channel_id),)
    )

def delete_expired_snipes(cutoff: datetime):
    """Delete all snipe rows older than the cutoff datetime."""
    cutoff_str = cutoff.isoformat()
    with get_connection() as conn:
        conn.execute("DELETE FROM snipes_messages  WHERE time < ?", (cutoff_str,))
        conn.execute("DELETE FROM snipes_reactions WHERE time < ?", (cutoff_str,))
        conn.execute("DELETE FROM snipes_edits     WHERE time < ?", (cutoff_str,))