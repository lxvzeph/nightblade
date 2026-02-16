import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "/data/bot.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS autoresponders (
            guild_id TEXT NOT NULL,
            trigger TEXT NOT NULL,
            response TEXT,
            attachment TEXT,
            filename TEXT,
            PRIMARY KEY (guild_id, trigger)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS prefixes (
            guild_id TEXT PRIMARY KEY,
            prefix TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS imute_config (
            guild_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS rmute_config (
            guild_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            guild_id TEXT NOT NULL,
            case_num INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            mod_id TEXT NOT NULL,
            type TEXT NOT NULL,
            reason TEXT,
            timestamp INTEGER NOT NULL,
            PRIMARY KEY (guild_id, case_num)
            )
            """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS case_counters (
            guild_id TEXT PRIMARY KEY,
            case_counter INTEGER NOT NULL DEFAULT 0
            )
            """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            mod_id TEXT NOT NULL,
            reason TEXT,
            timestamp INTEGER NOT NULL,
            case_num INTEGER
            )
            """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS role_backup_members (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
            )
            """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS role_backup (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, role_id)
            )
            """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS snipes_messages (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id        TEXT NOT NULL,
            author_id         TEXT NOT NULL,
            author_name       TEXT NOT NULL,
            author_avatar_url TEXT,
            content           TEXT,
            attachments       TEXT,
            time              TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS snipes_reactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id        TEXT NOT NULL,
            user_id           TEXT NOT NULL,
            user_name         TEXT NOT NULL,
            user_avatar_url   TEXT,
            emoji             TEXT NOT NULL,
            message_id        TEXT NOT NULL,
            message_url       TEXT NOT NULL,
            time              TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS snipes_edits (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id        TEXT NOT NULL,
            author_id         TEXT NOT NULL,
            author_name       TEXT NOT NULL,
            author_avatar_url TEXT,
            before_content    TEXT,
            after_content     TEXT,
            message_url       TEXT NOT NULL,
            time              TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS timezones (
            user_id TEXT PRIMARY KEY,
            timezone TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS sticky_messages (
            channel_id TEXT PRIMARY KEY,
            content TEXT,
            embeds TEXT,
            attachments TEXT,
            message_id TEXT NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            guild_id TEXT PRIMARY KEY,
            key TEXT NOT NULL,
            activated INTEGER NOT NULL DEFAULT 0
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS autoroles (
            guild_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jail_config (
            guild_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL,
            channel_id TEXT NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS disabled_commands (
            guild_id TEXT NOT NULL,
            command_name TEXT NOT NULL,
            channel_id TEXT NOT NULL DEFAULT '0',
            PRIMARY KEY (guild_id, command_name, channel_id)
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS command_restrictions (
            guild_id TEXT NOT NULL,
            command_name TEXT NOT NULL,
            type TEXT NOT NULL,
            value_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, command_name, type, value_id)
        )
        """)