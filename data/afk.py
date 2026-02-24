from data.db import get_connection
import time

TWODAYS = 60 * 60 * 24 * 2

def set_afk(user_id: int, status: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO afk_users (user_id, status, timestamp) VALUES (?, ?, ?)",
            (str(user_id), status, int(time.time()))
        )

def get_afk(user_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT status, timestamp FROM afk_users WHERE user_id = ?",
            (str(user_id),)
        )
        result = cur.fetchone()
        
        # Auto-cleanup if AFK status is older than 2 days
        if result:
            status, timestamp = result
            if int(time.time()) - timestamp > TWODAYS:
                remove_afk(user_id)
                return None
        
        return result

def remove_afk(user_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM afk_users WHERE user_id = ?",
            (str(user_id),)
        )

def add_mention(guild_id: int, afk_user_id: int, mentioner_id: int, channel_id: int, message_id: int):
    with get_connection() as conn:
        # Clean old mentions before adding new one
        cutoff = int(time.time()) - TWODAYS
        conn.execute(
            "DELETE FROM afk_mentions WHERE afk_user_id = ? AND guild_id = ? AND timestamp < ?",
            (str(afk_user_id), str(guild_id), cutoff)
        )
        
        conn.execute(
            "INSERT INTO afk_mentions (guild_id, afk_user_id, mentioner_id, channel_id, message_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (str(guild_id), str(afk_user_id), str(mentioner_id), str(channel_id), str(message_id), int(time.time()))
        )

def get_mentions(afk_user_id: int, guild_id: int = None):
    cutoff = int(time.time()) - TWODAYS
    
    with get_connection() as conn:
        if guild_id:
            cur = conn.execute(
                "SELECT guild_id, mentioner_id, channel_id, message_id, timestamp FROM afk_mentions WHERE afk_user_id = ? AND guild_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
                (str(afk_user_id), str(guild_id), cutoff)
            )
        else:
            cur = conn.execute(
                "SELECT guild_id, mentioner_id, channel_id, message_id, timestamp FROM afk_mentions WHERE afk_user_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
                (str(afk_user_id), cutoff)
            )
        return cur.fetchall()

def cleanup_old_afk():
    cutoff = int(time.time()) - TWODAYS
    
    with get_connection() as conn:

        conn.execute(
            "DELETE FROM afk_users WHERE timestamp < ?",
            (cutoff,)
        )
        
        conn.execute(
            "DELETE FROM afk_mentions WHERE timestamp < ?",
            (cutoff,)
        )