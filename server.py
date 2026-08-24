import os
import time
import secrets
import sqlite3
import urllib.parse

import requests

from flask import Flask, request, send_file, redirect, jsonify


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

CLIENT_ID = os.getenv(
    "DISCORD_CLIENT_ID",
    "1541460139465506907"
)

CLIENT_SECRET = os.getenv(
    "DISCORD_CLIENT_SECRET"
)

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8080"
).rstrip("/")

BOT_API_KEY = os.getenv(
    "BOT_API_KEY"
)

# Use an absolute path so Render always uses the same DB
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "giveaway_tracker.db"
)

DISCORD_API = "https://discord.com/api/v10"


# ============================================================
# DATABASE
# ============================================================

def database():
    return sqlite3.connect(
        DATABASE,
        timeout=30
    )


def init_database():

    print()
    print("=" * 60)
    print("🗄️ INITIALIZING DATABASE")
    print("=" * 60)
    print("Database:", DATABASE)

    db = database()

    cursor = db.cursor()

    # --------------------------------------------------------
    # OAuth users
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_users (

            user_id TEXT PRIMARY KEY,

            access_token TEXT NOT NULL,

            refresh_token TEXT,

            expires_at INTEGER NOT NULL

        )
    """)

    # --------------------------------------------------------
    # OAuth states
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (

            state TEXT PRIMARY KEY,

            user_id TEXT NOT NULL,

            created_at INTEGER NOT NULL

        )
    """)

    db.commit()

    # --------------------------------------------------------
    # Verify tables actually exist
    # --------------------------------------------------------

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
    """)

    tables = [
        row[0]
        for row in cursor.fetchall()
    ]

    db.close()

    print("Tables:", tables)

    if "oauth_users" in tables:
        print("✅ oauth_users exists")
    else:
        print("❌ oauth_users MISSING")

    if "oauth_states" in tables:
        print("✅ oauth_states exists")
    else:
        print("❌ oauth_states MISSING")

    print("=" * 60)
    print()


# IMPORTANT:
# Render/Gunicorn imports this file instead of running it
# as __main__, so database initialization MUST happen here.
init_database()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online"
    })


# ============================================================
# START
# ============================================================

@app.route("/start")
def start():

    return """
    <html>

    <head>
        <title>Giveaway Tracker</title>
    </head>

    <body style="
        background:#111827;
        color:white;
        font-family:Arial;
        text-align:center;
        padding-top:100px;
    ">

        <h1>Giveaway Tracker</h1>

        <p>
            Please open this page from the
            Discord bot authorization button.
        </p>

    </body>

    </html>
    """


# ============================================================
# AUTHORIZE
# ============================================================

@app.route("/authorize")
def authorize():

    user_id = request.args.get(
        "user_id"
    )

    if not user_id:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Missing Discord user."
            )
        )

    user_id = str(user_id)

    # --------------------------------------------------------
    # Make sure database exists
    # --------------------------------------------------------

    init_database()

    # --------------------------------------------------------
    # Create OAuth state
    # --------------------------------------------------------

    state = secrets.token_urlsafe(32)

    db = database()

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO oauth_states (
            state,
            user_id,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        state,
        user_id,
        int(time.time())
    ))

    db.commit()
    db.close()

    # --------------------------------------------------------
    # Discord OAuth redirect
    # --------------------------------------------------------

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "identify guilds.join",
        "state": state
    }

    discord_url = (
        "https://discord.com/oauth2/authorize?"
        + urllib.parse.urlencode(params)
    )

    print(
        "🔐 Starting OAuth for user:",
        user_id
    )

    return redirect(
        discord_url
    )


# ============================================================
# CALLBACK
# ============================================================

@app.route("/callback")
def callback():

    code = request.args.get(
        "code"
    )

    state = request.args.get(
        "state"
    )

    error = request.args.get(
        "error"
    )

    # --------------------------------------------------------
    # OAuth cancelled
    # --------------------------------------------------------

    if error:

        print(
            "❌ OAuth cancelled:",
            error
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Authorization cancelled."
            )
        )

    # --------------------------------------------------------
    # Validate callback
    # --------------------------------------------------------

    if not code or not state:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid OAuth callback."
            )
        )

    # --------------------------------------------------------
    # Find state
    # --------------------------------------------------------

    db = database()

    cursor = db.cursor()

    cursor.execute("""
        SELECT
            user_id,
            created_at
        FROM oauth_states
        WHERE state = ?
    """, (
        state,
    ))

    row = cursor.fetchone()

    # State can only be used once
    cursor.execute("""
        DELETE FROM oauth_states
        WHERE state = ?
    """, (
        state,
    ))

    db.commit()
    db.close()

    if not row:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid or expired authorization."
            )
        )

    user_id = row[0]

    created_at = row[1]

    # --------------------------------------------------------
    # State expiration
    # --------------------------------------------------------

    if (
        int(time.time())
        - int(created_at)
        > 600
    ):

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Authorization expired."
            )
        )

    # --------------------------------------------------------
    # Check client secret
    # --------------------------------------------------------

    if not CLIENT_SECRET:

        print(
            "❌ DISCORD_CLIENT_SECRET is missing!"
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord OAuth is not configured."
            )
        )

    # --------------------------------------------------------
    # Exchange OAuth code
    # --------------------------------------------------------

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )

    try:

        response = requests.post(

            f"{DISCORD_API}/oauth2/token",

            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            },

            timeout=20
        )

    except requests.RequestException as e:

        print(
            "❌ Discord token request failed:",
            e
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Could not connect to Discord."
            )
        )

    # --------------------------------------------------------
    # Check Discord response
    # --------------------------------------------------------

    if response.status_code != 200:

        print(
            "❌ Discord token error:",
            response.status_code
        )

        print(
            response.text
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord token exchange failed."
            )
        )

    try:

        token = response.json()

    except Exception:

        print(
            "❌ Discord returned invalid JSON."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid Discord response."
            )
        )

    # --------------------------------------------------------
    # Get tokens
    # --------------------------------------------------------

    access_token = token.get(
        "access_token"
    )

    refresh_token = token.get(
        "refresh_token"
    )

    expires_in = int(
        token.get(
            "expires_in",
            604800
        )
    )

    if not access_token:

        print(
            "❌ No access token received."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "No access token received."
            )
        )

    # --------------------------------------------------------
    # Get Discord account
    # --------------------------------------------------------

    try:

        response = requests.get(

            f"{DISCORD_API}/users/@me",

            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=20
        )

    except requests.RequestException as e:

        print(
            "❌ Discord user request failed:",
            e
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Could not contact Discord."
            )
        )

    if response.status_code != 200:

        print(
            "❌ Could not get Discord user:",
            response.status_code
        )

        print(
            response.text
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Could not identify Discord account."
            )
        )

    discord_user = response.json()

    discord_user_id = str(
        discord_user.get("id")
    )

    # --------------------------------------------------------
    # Verify user
    # --------------------------------------------------------

    if discord_user_id != str(user_id):

        print(
            "❌ Discord account mismatch."
        )

        print(
            "Expected:",
            user_id
        )

        print(
            "Received:",
            discord_user_id
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord account mismatch."
            )
        )

    # --------------------------------------------------------
    # Save authorization
    # --------------------------------------------------------

    expires_at = (
        int(time.time())
        + expires_in
    )

    db = database()

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO oauth_users (
            user_id,
            access_token,
            refresh_token,
            expires_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id)

        DO UPDATE SET

            access_token =
                excluded.access_token,

            refresh_token =
                excluded.refresh_token,

            expires_at =
                excluded.expires_at
    """, (
        str(user_id),
        access_token,
        refresh_token,
        expires_at
    ))

    db.commit()
    db.close()

    # --------------------------------------------------------
    # Success log
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("🔐 DISCORD ACCOUNT AUTHORIZED")
    print("=" * 60)

    print(
        "Username:",
        discord_user.get("username")
    )

    print(
        "User ID:",
        discord_user_id
    )

    print(
        "Expires:",
        expires_at
    )

    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Back to website
    # --------------------------------------------------------

    return redirect(
        "/?success=1"
    )


# ============================================================
# BOT API - GET ONE USER
# ============================================================

@app.route(
    "/api/oauth/<user_id>"
)
def get_oauth(user_id):

    # --------------------------------------------------------
    # Security
    # --------------------------------------------------------

    if (
        not BOT_API_KEY
        or request.headers.get("X-Bot-Key")
        != BOT_API_KEY
    ):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    db = database()

    cursor = db.cursor()

    cursor.execute("""
        SELECT
            access_token,
            refresh_token,
            expires_at
        FROM oauth_users
        WHERE user_id = ?
    """, (
        str(user_id),
    ))

    row = cursor.fetchone()

    db.close()

    # --------------------------------------------------------
    # Not authorized
    # --------------------------------------------------------

    if not row:

        return jsonify({
            "authorized": False
        })

    # --------------------------------------------------------
    # Authorized
    # --------------------------------------------------------

    return jsonify({

        "authorized": True,

        "access_token":
            row[0],

        "refresh_token":
            row[1],

        "expires_at":
            row[2]

    })


# ============================================================
# BOT API - ALL AUTHORIZED USERS
# ============================================================

@app.route(
    "/api/authorized"
)
def authorized_users():

    # --------------------------------------------------------
    # Security
    # --------------------------------------------------------

    if (
        not BOT_API_KEY
        or request.headers.get("X-Bot-Key")
        != BOT_API_KEY
    ):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    db = database()

    cursor = db.cursor()

    cursor.execute("""
        SELECT user_id
        FROM oauth_users
    """)

    rows = cursor.fetchall()

    db.close()

    # --------------------------------------------------------
    # Return users
    # --------------------------------------------------------

    users = [
        str(row[0])
        for row in rows
    ]

    print(
        f"📋 Authorized users: {len(users)}"
    )

    return jsonify({
        "users": users
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "8080"
        )
    )

    print()
    print("=" * 60)
    print("🌐 GIVEAWAY TRACKER WEBSITE")
    print("=" * 60)
    print(
        f"Running on port {port}"
    )
    print(
        f"Public URL: {PUBLIC_URL}"
    )
    print(
        f"Database: {DATABASE}"
    )
    print("=" * 60)
    print()

    app.run(
        host="0.0.0.0",
        port=port
    )