import os, sqlite3, threading, time

DB_PATH = os.getenv('DATABASE_PATH', 'giveaway_tracker.db')
LOCK = threading.RLock()

def connect():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with LOCK, connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS auto_join (
            user_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS detected_giveaways (
            message_id TEXT PRIMARY KEY,
            guild_id TEXT,
            channel_id TEXT,
            author_id TEXT,
            jump_url TEXT,
            invite_url TEXT,
            prize TEXT,
            winners INTEGER,
            detected_at REAL NOT NULL
        );
        ''')
        c.commit()

def set_auto_join(user_id, enabled):
    now=time.time()
    with LOCK, connect() as c:
        c.execute('''INSERT INTO auto_join(user_id,enabled,created_at,updated_at) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at''',
                  (str(user_id), int(enabled), now, now))
        c.commit()

def is_auto_join_enabled(user_id):
    with LOCK, connect() as c:
        r=c.execute('SELECT enabled FROM auto_join WHERE user_id=?',(str(user_id),)).fetchone()
        return bool(r and r['enabled'])

def get_enabled_users():
    with LOCK, connect() as c:
        return [str(r['user_id']) for r in c.execute('SELECT user_id FROM auto_join WHERE enabled=1').fetchall()]

def giveaway_seen(message_id):
    with LOCK, connect() as c:
        return c.execute('SELECT 1 FROM detected_giveaways WHERE message_id=?',(str(message_id),)).fetchone() is not None

def save_giveaway(message_id,guild_id,channel_id,author_id,jump_url,invite_url,prize,winners):
    with LOCK, connect() as c:
        r=c.execute('''INSERT OR IGNORE INTO detected_giveaways
        (message_id,guild_id,channel_id,author_id,jump_url,invite_url,prize,winners,detected_at)
        VALUES(?,?,?,?,?,?,?,?,?)''',(str(message_id),str(guild_id) if guild_id else None,str(channel_id),str(author_id),jump_url,invite_url,prize,winners,time.time()))
        c.commit(); return r.rowcount==1
