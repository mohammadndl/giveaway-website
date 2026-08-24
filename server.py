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

    db = database()
    cursor = db.cursor()

    # --------------------------------------------------------
    # Authorized Discord users
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_users (

            user_id TEXT PRIMARY KEY,

            username TEXT,

            access_token TEXT NOT NULL,

            refresh_token TEXT,

            expires_at INTEGER NOT NULL,

            created_at INTEGER NOT NULL

        )
    """)

    # --------------------------------------------------------
    # OAuth states
    #
    # IMPORTANT:
    # There is NO user_id here anymore.
    #
    # We don't know the user's Discord ID until Discord
    # sends us back the OAuth callback.
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (

            state TEXT PRIMARY KEY,

            created_at INTEGER NOT NULL

        )
    """)

    db.commit()
    db.close()

    print(
        "✅ Database initialized:",
        DATABASE
    )


# IMPORTANT:
# This runs when Render/Gunicorn imports server.py.
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
# AUTO PAGE
# ============================================================

@app.route("/auto")
def auto():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


# ============================================================
# AUTHORIZE
#
# IMPORTANT:
# NO ?user_id= REQUIRED
#
# The user ID is obtained AFTER Discord authorization.
# ============================================================

@app.route("/authorize")
def authorize():

    # --------------------------------------------------------
    # Check Discord client secret
    # --------------------------------------------------------

    if not CLIENT_SECRET:

        print(
            "❌ DISCORD_CLIENT_SECRET is missing."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord OAuth is not configured."
            )
        )

    # --------------------------------------------------------
    # Generate OAuth state
    # --------------------------------------------------------

    state = secrets.token_urlsafe(32)

    # --------------------------------------------------------
    # Save state
    # --------------------------------------------------------

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO oauth_states (
            state,
            created_at
        )
        VALUES (?, ?)
    """, (
        state,
        int(time.time())
    ))

    db.commit()
    db.close()

    # --------------------------------------------------------
    # Discord callback
    # --------------------------------------------------------

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )

    # --------------------------------------------------------
    # Discord OAuth parameters
    # --------------------------------------------------------

    params = {

        "client_id":
            CLIENT_ID,

        "response_type":
            "code",

        "redirect_uri":
            redirect_uri,

        "scope":
            "identify",

        "state":
            state

    }

    discord_url = (
        "https://discord.com/oauth2/authorize?"
        + urllib.parse.urlencode(params)
    )

    print()
    print("=" * 60)
    print("🔐 STARTING DISCORD AUTHORIZATION")
    print("=" * 60)
    print(
        "Redirect URI:",
        redirect_uri
    )
    print("=" * 60)

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
    # User cancelled
    # --------------------------------------------------------

    if error:

        print(
            "❌ Discord OAuth error:",
            error
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord authorization was cancelled."
            )
        )

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    if not code or not state:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid Discord authorization callback."
            )
        )

    # --------------------------------------------------------
    # Find OAuth state
    # --------------------------------------------------------

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            created_at
        FROM oauth_states
        WHERE state = ?
    """, (
        state,
    ))

    row = cursor.fetchone()

    # Delete state immediately.
    #
    # This prevents replaying the same OAuth callback.
    cursor.execute("""
        DELETE FROM oauth_states
        WHERE state = ?
    """, (
        state,
    ))

    db.commit()
    db.close()

    # --------------------------------------------------------
    # State doesn't exist
    # --------------------------------------------------------

    if not row:

        print(
            "❌ Invalid OAuth state."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid or expired authorization."
            )
        )

    created_at = row[0]

    # --------------------------------------------------------
    # State expiration
    # --------------------------------------------------------

    if (
        int(time.time())
        - int(created_at)
        > 600
    ):

        print(
            "❌ OAuth state expired."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Authorization expired. Please try again."
            )
        )

    # ========================================================
    # EXCHANGE CODE FOR TOKEN
    # ========================================================

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )

    try:

        response = requests.post(

            f"{DISCORD_API}/oauth2/token",

            data={

                "client_id":
                    CLIENT_ID,

                "client_secret":
                    CLIENT_SECRET,

                "grant_type":
                    "authorization_code",

                "code":
                    code,

                "redirect_uri":
                    redirect_uri

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
    # Token exchange failed
    # --------------------------------------------------------

    if response.status_code != 200:

        print(
            "❌ Discord OAuth token error:",
            response.status_code
        )

        print(
            response.text
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord authorization failed."
            )
        )

    # --------------------------------------------------------
    # Parse token
    # --------------------------------------------------------

    try:

        token = response.json()

    except Exception:

        print(
            "❌ Discord returned invalid token JSON."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid Discord response."
            )
        )

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
            "❌ Discord did not provide an access token."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "No Discord access token received."
            )
        )

    # ========================================================
    # GET DISCORD USER
    # ========================================================

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
                "Could not retrieve your Discord account."
            )
        )

    # --------------------------------------------------------
    # User request failed
    # --------------------------------------------------------

    if response.status_code != 200:

        print(
            "❌ Discord /users/@me failed:",
            response.status_code
        )

        print(
            response.text
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Could not identify your Discord account."
            )
        )

    # --------------------------------------------------------
    # Discord user
    # --------------------------------------------------------

    discord_user = response.json()

    discord_user_id = discord_user.get(
        "id"
    )

    username = discord_user.get(
        "username"
    )

    if not discord_user_id:

        print(
            "❌ Discord user ID missing."
        )

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord account ID was not received."
            )
        )

    discord_user_id = str(
        discord_user_id
    )

    # ========================================================
    # SAVE AUTHORIZED USER
    # ========================================================

    expires_at = (
        int(time.time())
        + expires_in
    )

    created_at = int(
        time.time()
    )

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO oauth_users (

            user_id,

            username,

            access_token,

            refresh_token,

            expires_at,

            created_at

        )

        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(user_id)

        DO UPDATE SET

            username =
                excluded.username,

            access_token =
                excluded.access_token,

            refresh_token =
                excluded.refresh_token,

            expires_at =
                excluded.expires_at
    """, (

        discord_user_id,

        username,

        access_token,

        refresh_token,

        expires_at,

        created_at

    ))

    db.commit()
    db.close()

    # ========================================================
    # LOG
    # ========================================================

    print()
    print("=" * 60)
    print("✅ DISCORD USER AUTHORIZED")
    print("=" * 60)
    print(
        "Username:",
        username
    )
    print(
        "User ID:",
        discord_user_id
    )
    print("=" * 60)
    print()

    # ========================================================
    # RETURN TO WEBSITE
    # ========================================================

    return redirect(
        "/?success=1"
    )


# ============================================================
# BOT API
#
# GET ONE USER
# ============================================================

@app.route(
    "/api/oauth/<user_id>"
)
def get_oauth(user_id):

    # --------------------------------------------------------
    # API security
    # --------------------------------------------------------

    if (
        not BOT_API_KEY
        or request.headers.get(
            "X-Bot-Key"
        ) != BOT_API_KEY
    ):

        return jsonify({
            "error":
                "Unauthorized"
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
    # User hasn't authorized
    # --------------------------------------------------------

    if not row:

        return jsonify({

            "authorized":
                False

        })

    # --------------------------------------------------------
    # User authorized
    # --------------------------------------------------------

    return jsonify({

        "authorized":
            True,

        "access_token":
            row[0],

        "refresh_token":
            row[1],

        "expires_at":
            row[2]

    })


# ============================================================
# BOT API
#
# GET ALL AUTHORIZED USERS
# ============================================================

@app.route(
    "/api/authorized"
)
def authorized_users():

    # --------------------------------------------------------
    # API security
    # --------------------------------------------------------

    if (
        not BOT_API_KEY
        or request.headers.get(
            "X-Bot-Key"
        ) != BOT_API_KEY
    ):

        return jsonify({
            "error":
                "Unauthorized"
        }), 401

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            user_id
        FROM oauth_users
    """)

    rows = cursor.fetchall()

    db.close()

    users = [

        str(row[0])

        for row in rows

    ]

    print(
        f"📋 Authorized users: {len(users)}"
    )

    return jsonify({

        "users":
            users

    })


# ============================================================
# OPTIONAL API
#
# Check if a user is authorized.
# Useful for your /auto page.
# ============================================================

@app.route(
    "/api/check/<user_id>"
)
def check_authorized(user_id):

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            user_id,
            username
        FROM oauth_users
        WHERE user_id = ?
    """, (
        str(user_id),
    ))

    row = cursor.fetchone()

    db.close()

    if not row:

        return jsonify({

            "authorized":
                False

        })

    return jsonify({

        "authorized":
            True,

        "user_id":
            row[0],

        "username":
            row[1]

    })


# ============================================================
# CLEAN OLD OAUTH STATES
# ============================================================

def cleanup_oauth_states():

    cutoff = (
        int(time.time())
        - 3600
    )

    db = database()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM oauth_states
        WHERE created_at < ?
    """, (
        cutoff,
    ))

    db.commit()
    db.close()


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

    cleanup_oauth_states()

    print()
    print("=" * 60)
    print("🌐 GIVEAWAY TRACKER WEBSITE")
    print("=" * 60)
    print(
        "Port:",
        port
    )
    print(
        "Public URL:",
        PUBLIC_URL
    )
    print(
        "Database:",
        DATABASE
    )
    print("=" * 60)
    print()

    app.run(
        host="0.0.0.0",
        port=port
    )