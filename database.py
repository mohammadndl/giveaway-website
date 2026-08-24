import os, sqlite3, threading, time
DB_PATH=os.getenv('DATABASE_PATH','giveaway_tracker.db'); LOCK=threading.RLock()
def db():
 c=sqlite3.connect(DB_PATH,timeout=30); c.row_factory=sqlite3.Row; return c
def init_db():
 with LOCK,db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS auto_join(user_id TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_states(state TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS oauth_users(user_id TEXT PRIMARY KEY,access_token TEXT NOT NULL,refresh_token TEXT,expires_at REAL,token_type TEXT,scope TEXT,updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS detected_giveaways(message_id TEXT PRIMARY KEY,guild_id TEXT,channel_id TEXT,author_id TEXT,detected_at REAL NOT NULL);'''); c.commit()
def set_auto_join(uid,enabled):
 with LOCK,db() as c:
  c.execute('INSERT INTO auto_join VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at',(str(uid),int(enabled),time.time())); c.commit()
def is_auto_join_enabled(uid):
 with LOCK,db() as c:
  r=c.execute('SELECT enabled FROM auto_join WHERE user_id=?',(str(uid),)).fetchone(); return bool(r and r['enabled'])
def create_oauth_state(state,uid):
 with LOCK,db() as c: c.execute('INSERT INTO oauth_states VALUES(?,?,?,0)',(state,str(uid),time.time())); c.commit()
def consume_oauth_state(state,ttl=600):
 with LOCK,db() as c:
  r=c.execute('SELECT user_id,created_at,used FROM oauth_states WHERE state=?',(state,)).fetchone()
  if not r or r['used'] or time.time()-r['created_at']>ttl: return None
  cur=c.execute('UPDATE oauth_states SET used=1 WHERE state=? AND used=0',(state,)); c.commit()
  return str(r['user_id']) if cur.rowcount==1 else None
def save_oauth_user(uid,access,refresh,expires,token_type,scope):
 with LOCK,db() as c:
  c.execute('''INSERT INTO oauth_users VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET access_token=excluded.access_token,refresh_token=excluded.refresh_token,expires_at=excluded.expires_at,token_type=excluded.token_type,scope=excluded.scope,updated_at=excluded.updated_at''',(str(uid),access,refresh,expires,token_type,scope,time.time())); c.commit()
def get_oauth_user(uid):
 with LOCK,db() as c:
  r=c.execute('SELECT * FROM oauth_users WHERE user_id=?',(str(uid),)).fetchone(); return dict(r) if r else None
def is_user_authorized(uid): return get_oauth_user(uid) is not None
def giveaway_already_detected(mid):
 with LOCK,db() as c: return c.execute('SELECT 1 FROM detected_giveaways WHERE message_id=?',(str(mid),)).fetchone() is not None
def mark_giveaway_detected(mid,guild,channel,author):
 with LOCK,db() as c:
  cur=c.execute('INSERT OR IGNORE INTO detected_giveaways VALUES(?,?,?,?,?)',(str(mid),guild,channel,author,time.time())); c.commit(); return cur.rowcount==1
