import os
import sqlite3
import threading
import time


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "giveaway_tracker.db"
)

_lock = threading.RLock()


def _connect():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        with _connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS auto_join (
                    user_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS oauth_users (
                    user_id TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at REAL,
                    token_type TEXT,
                    scope TEXT,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS detected_giveaways (
                    message_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    channel_id TEXT,
                    author_id TEXT,
                    detected_at REAL NOT NULL
                );
            """)

            conn.commit()


def set_auto_join(user_id, enabled):
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO auto_join
                    (user_id, enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    str(user_id),
                    1 if enabled else 0,
                    time.time()
                )
            )

            conn.commit()


def is_auto_join_enabled(user_id):
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT enabled
                FROM auto_join
                WHERE user_id = ?
                """,
                (str(user_id),)
            ).fetchone()

            return bool(
                row and row["enabled"]
            )


def create_oauth_state(
    state,
    user_id
):
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO oauth_states
                    (state, user_id, created_at, used)
                VALUES (?, ?, ?, 0)
                """,
                (
                    str(state),
                    str(user_id),
                    time.time()
                )
            )

            conn.commit()


def consume_oauth_state(
    state,
    max_age=600
):
    now = time.time()

    with _lock:
        with _connect() as conn:

            row = conn.execute(
                """
                SELECT
                    user_id,
                    created_at,
                    used
                FROM oauth_states
                WHERE state = ?
                """,
                (str(state),)
            ).fetchone()

            if row is None:
                return None

            if row["used"]:
                return None

            if now - float(row["created_at"]) > max_age:

                conn.execute(
                    """
                    DELETE FROM oauth_states
                    WHERE state = ?
                    """,
                    (str(state),)
                )

                conn.commit()

                return None

            result = conn.execute(
                """
                UPDATE oauth_states
                SET used = 1
                WHERE state = ?
                AND used = 0
                """,
                (str(state),)
            )

            conn.commit()

            if result.rowcount != 1:
                return None

            return str(row["user_id"])


def save_oauth_user(
    user_id,
    access_token,
    refresh_token=None,
    expires_at=None,
    token_type=None,
    scope=None
):
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO oauth_users (
                    user_id,
                    access_token,
                    refresh_token,
                    expires_at,
                    token_type,
                    scope,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    access_token =
                        excluded.access_token,

                    refresh_token =
                        excluded.refresh_token,

                    expires_at =
                        excluded.expires_at,

                    token_type =
                        excluded.token_type,

                    scope =
                        excluded.scope,

                    updated_at =
                        excluded.updated_at
                """,
                (
                    str(user_id),
                    access_token,
                    refresh_token,
                    expires_at,
                    token_type,
                    scope,
                    time.time()
                )
            )

            conn.commit()


def get_oauth_user(user_id):
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM oauth_users
                WHERE user_id = ?
                """,
                (str(user_id),)
            ).fetchone()

            if row is None:
                return None

            return dict(row)


def is_user_authorized(user_id):
    return (
        get_oauth_user(user_id)
        is not None
    )


def mark_giveaway_detected(
    message_id,
    guild_id=None,
    channel_id=None,
    author_id=None
):
    with _lock:
        with _connect() as conn:
            result = conn.execute(
                """
                INSERT OR IGNORE INTO detected_giveaways (
                    message_id,
                    guild_id,
                    channel_id,
                    author_id,
                    detected_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(message_id),

                    str(guild_id)
                    if guild_id is not None
                    else None,

                    str(channel_id)
                    if channel_id is not None
                    else None,

                    str(author_id)
                    if author_id is not None
                    else None,

                    time.time()
                )
            )

            conn.commit()

            return result.rowcount == 1


def giveaway_already_detected(
    message_id
):
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM detected_giveaways
                WHERE message_id = ?
                """,
                (str(message_id),)
            ).fetchone()

            return row is not None