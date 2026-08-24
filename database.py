import os
import sqlite3
import threading
import time


DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "giveaway_tracker.db"
)

_DB_LOCK = threading.RLock()


def _connect():
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    with _DB_LOCK:
        connection = _connect()

        try:
            connection.execute("PRAGMA journal_mode=WAL")

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS auto_join (
                    user_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS detected_giveaways (
                    message_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    channel_id TEXT NOT NULL,
                    jump_url TEXT NOT NULL,
                    prize TEXT,
                    winner_count INTEGER,
                    invite_url TEXT,
                    detected_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS giveaway_participants (
                    message_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    joined_at REAL NOT NULL,

                    PRIMARY KEY (
                        message_id,
                        user_id
                    )
                );

                CREATE INDEX IF NOT EXISTS
                idx_auto_join_enabled
                ON auto_join(enabled);

                CREATE INDEX IF NOT EXISTS
                idx_giveaway_participants_message
                ON giveaway_participants(message_id);
                """
            )

            connection.commit()

        finally:
            connection.close()


def set_auto_join(user_id: int, enabled: bool):
    now = time.time()

    with _DB_LOCK:
        connection = _connect()

        try:
            connection.execute(
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
                    1 if enabled else 0,
                    now,
                    now
                )
            )

            connection.commit()

        finally:
            connection.close()


def auto_join_enabled(user_id: int) -> bool:
    with _DB_LOCK:
        connection = _connect()

        try:
            row = connection.execute(
                """
                SELECT enabled
                FROM auto_join
                WHERE user_id = ?
                """,
                (str(user_id),)
            ).fetchone()

            if row is None:
                return False

            return bool(row["enabled"])

        finally:
            connection.close()


def get_auto_join_users():
    with _DB_LOCK:
        connection = _connect()

        try:
            rows = connection.execute(
                """
                SELECT user_id
                FROM auto_join
                WHERE enabled = 1
                """
            ).fetchall()

            users = []

            for row in rows:
                try:
                    users.append(int(row["user_id"]))
                except (TypeError, ValueError):
                    continue

            return users

        finally:
            connection.close()


def giveaway_exists(message_id: int) -> bool:
    with _DB_LOCK:
        connection = _connect()

        try:
            row = connection.execute(
                """
                SELECT 1
                FROM detected_giveaways
                WHERE message_id = ?
                LIMIT 1
                """,
                (str(message_id),)
            ).fetchone()

            return row is not None

        finally:
            connection.close()


def save_detected_giveaway(
    message_id: int,
    guild_id,
    channel_id: int,
    jump_url: str,
    prize: str,
    winner_count,
    invite_url
):
    with _DB_LOCK:
        connection = _connect()

        try:
            connection.execute(
                """
                INSERT OR IGNORE INTO detected_giveaways (
                    message_id,
                    guild_id,
                    channel_id,
                    jump_url,
                    prize,
                    winner_count,
                    invite_url,
                    detected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(message_id),
                    str(guild_id) if guild_id else None,
                    str(channel_id),
                    jump_url,
                    prize,
                    winner_count,
                    invite_url,
                    time.time()
                )
            )

            connection.commit()

        finally:
            connection.close()


def add_participant(
    message_id: int,
    user_id: int
) -> bool:

    with _DB_LOCK:
        connection = _connect()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO giveaway_participants (
                    message_id,
                    user_id,
                    joined_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    str(message_id),
                    str(user_id),
                    time.time()
                )
            )

            connection.commit()

            return cursor.rowcount > 0

        finally:
            connection.close()


def remove_participant(
    message_id: int,
    user_id: int
) -> bool:

    with _DB_LOCK:
        connection = _connect()

        try:
            cursor = connection.execute(
                """
                DELETE FROM giveaway_participants
                WHERE message_id = ?
                AND user_id = ?
                """,
                (
                    str(message_id),
                    str(user_id)
                )
            )

            connection.commit()

            return cursor.rowcount > 0

        finally:
            connection.close()


def get_participants(message_id: int):
    with _DB_LOCK:
        connection = _connect()

        try:
            rows = connection.execute(
                """
                SELECT user_id
                FROM giveaway_participants
                WHERE message_id = ?
                ORDER BY joined_at ASC
                """,
                (str(message_id),)
            ).fetchall()

            result = []

            for row in rows:
                try:
                    result.append(int(row["user_id"]))
                except (TypeError, ValueError):
                    continue

            return result

        finally:
            connection.close()


def count_participants(message_id: int) -> int:
    with _DB_LOCK:
        connection = _connect()

        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS amount
                FROM giveaway_participants
                WHERE message_id = ?
                """,
                (str(message_id),)
            ).fetchone()

            return int(row["amount"])

        finally:
            connection.close()


def clear_participants(message_id: int):
    with _DB_LOCK:
        connection = _connect()

        try:
            connection.execute(
                """
                DELETE FROM giveaway_participants
                WHERE message_id = ?
                """,
                (str(message_id),)
            )

            connection.commit()

        finally:
            connection.close()