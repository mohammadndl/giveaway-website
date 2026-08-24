import os
import sqlite3
import threading
import time

DB_PATH = os.getenv("DATABASE_PATH", "giveaway_tracker.db")

LOCK = threading.RLock()


def connect():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with LOCK:

        with connect() as conn:

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS auto_join (
                    user_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS giveaways (
                    message_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    channel_id TEXT,
                    jump_url TEXT,
                    prize TEXT,
                    winners INTEGER,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS participants (
                    giveaway_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,

                    PRIMARY KEY (
                        giveaway_id,
                        user_id
                    )
                );
            """)

            conn.commit()


def set_auto_join(
    user_id,
    enabled
):

    now = time.time()

    with LOCK:

        with connect() as conn:

            conn.execute(
                """
                INSERT INTO auto_join (
                    user_id,
                    enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    str(user_id),
                    int(enabled),
                    now,
                    now
                )
            )

            conn.commit()


def auto_join_enabled(
    user_id
):

    with LOCK:

        with connect() as conn:

            row = conn.execute(
                """
                SELECT enabled
                FROM auto_join
                WHERE user_id = ?
                """,
                (
                    str(user_id),
                )
            ).fetchone()

            if row is None:
                return False

            return bool(
                row["enabled"]
            )


def get_auto_join_users():

    with LOCK:

        with connect() as conn:

            rows = conn.execute(
                """
                SELECT user_id
                FROM auto_join
                WHERE enabled = 1
                """
            ).fetchall()

            return [
                int(row["user_id"])
                for row in rows
            ]


def giveaway_exists(
    message_id
):

    with LOCK:

        with connect() as conn:

            row = conn.execute(
                """
                SELECT 1
                FROM giveaways
                WHERE message_id = ?
                """,
                (
                    str(message_id),
                )
            ).fetchone()

            return row is not None


def save_giveaway(
    message_id,
    guild_id,
    channel_id,
    jump_url,
    prize,
    winners
):

    with LOCK:

        with connect() as conn:

            conn.execute(
                """
                INSERT OR IGNORE INTO giveaways (
                    message_id,
                    guild_id,
                    channel_id,
                    jump_url,
                    prize,
                    winners,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(message_id),
                    str(guild_id)
                    if guild_id is not None
                    else None,
                    str(channel_id),
                    jump_url,
                    prize,
                    winners,
                    time.time()
                )
            )

            conn.commit()


def add_participant(
    giveaway_id,
    user_id
):

    with LOCK:

        with connect() as conn:

            conn.execute(
                """
                INSERT OR IGNORE INTO participants (
                    giveaway_id,
                    user_id
                )
                VALUES (?, ?)
                """,
                (
                    str(giveaway_id),
                    str(user_id)
                )
            )

            conn.commit()


def remove_participant(
    giveaway_id,
    user_id
):

    with LOCK:

        with connect() as conn:

            conn.execute(
                """
                DELETE FROM participants
                WHERE giveaway_id = ?
                AND user_id = ?
                """,
                (
                    str(giveaway_id),
                    str(user_id)
                )
            )

            conn.commit()


def get_participants(
    giveaway_id
):

    with LOCK:

        with connect() as conn:

            rows = conn.execute(
                """
                SELECT user_id
                FROM participants
                WHERE giveaway_id = ?
                """,
                (
                    str(giveaway_id),
                )
            ).fetchall()

            return [
                int(row["user_id"])
                for row in rows
            ]