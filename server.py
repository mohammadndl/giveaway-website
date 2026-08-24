from flask import Flask, send_file

app = Flask(__name__)

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/health")
def health():
    return {"status": "online"}

import os
import time
import secrets
import sqlite3
import urllib.parse

import requests

from flask import (
    Flask,
    request,
    send_file,
    redirect,
    jsonify
)


# ============================================================
# CONFIG
# ============================================================

app = Flask(__name__)


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


DATABASE = "giveaway_tracker.db"


DISCORD_API = (
    "https://discord.com/api/v10"
)


# ============================================================
# DATABASE
# ============================================================

def database():

    return sqlite3.connect(
        DATABASE
    )


def init_database():

    db = database()

    cursor = db.cursor()


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_users (

            user_id TEXT PRIMARY KEY,

            access_token TEXT NOT NULL,

            refresh_token TEXT,

            expires_at INTEGER NOT NULL

        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (

            state TEXT PRIMARY KEY,

            user_id TEXT NOT NULL,

            created_at INTEGER NOT NULL

        )
    """)


    db.commit()

    db.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return send_file(
        "index.html"
    )


# ============================================================
# START
#
# This is useful if you open the website directly.
# The Discord bot should normally send:
#
# /?user_id=DISCORD_USER_ID
# ============================================================

@app.route("/start")
def start():

    return """
    <html>

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
            "/?error=Missing%20Discord%20user"
        )


    # --------------------------------------------------------
    # CREATE STATE
    # --------------------------------------------------------

    state = secrets.token_urlsafe(
        32
    )


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

        str(user_id),

        int(time.time())
    ))


    db.commit()

    db.close()


    # --------------------------------------------------------
    # DISCORD REDIRECT
    # --------------------------------------------------------

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )


    params = {

        "client_id":
            CLIENT_ID,

        "response_type":
            "code",

        "redirect_uri":
            redirect_uri,

        "scope":
            "identify guilds.join",

        "state":
            state
    }


    discord_url = (
        "https://discord.com/oauth2/authorize?"
        + urllib.parse.urlencode(params)
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


    if error:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Authorization cancelled."
            )
        )


    if not code or not state:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Invalid OAuth callback."
            )
        )


    # --------------------------------------------------------
    # FIND STATE
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
    # STATE EXPIRATION
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
    # TOKEN REQUEST
    # --------------------------------------------------------

    redirect_uri = (
        f"{PUBLIC_URL}/callback"
    )


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


    if response.status_code != 200:

        print(
            "Discord token error:",
            response.text
        )


        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord token exchange failed."
            )
        )


    token = response.json()


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

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "No access token received."
            )
        )


    # --------------------------------------------------------
    # GET DISCORD ACCOUNT
    # --------------------------------------------------------

    response = requests.get(

        f"{DISCORD_API}/users/@me",

        headers={

            "Authorization":
                f"Bearer {access_token}"
        },

        timeout=20
    )


    if response.status_code != 200:

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Could not identify Discord account."
            )
        )


    discord_user = response.json()


    # --------------------------------------------------------
    # VERIFY USER
    # --------------------------------------------------------

    if str(
        discord_user["id"]
    ) != str(
        user_id
    ):

        return redirect(
            "/?error="
            + urllib.parse.quote(
                "Discord account mismatch."
            )
        )


    # --------------------------------------------------------
    # SAVE
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
        discord_user["id"]
    )
    print("=" * 60)


    # --------------------------------------------------------
    # BACK TO WEBSITE
    # --------------------------------------------------------

    return redirect(
        "/?success=1"
    )


# ============================================================
# BOT API
# ============================================================

@app.route(
    "/api/oauth/<user_id>"
)
def get_oauth(user_id):

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        request.headers.get(
            "X-Bot-Key"
        )
        != BOT_API_KEY
    ):

        return jsonify({
            "error":
                "Unauthorized"
        }), 401


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


    if not row:

        return jsonify({

            "authorized":
                False

        })


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
# ALL AUTHORIZED USERS
# ============================================================

@app.route(
    "/api/authorized"
)
def authorized_users():

    if (
        request.headers.get(
            "X-Bot-Key"
        )
        != BOT_API_KEY
    ):

        return jsonify({
            "error":
                "Unauthorized"
        }), 401


    db = database()

    cursor = db.cursor()


    cursor.execute("""
        SELECT user_id
        FROM oauth_users
    """)


    rows = cursor.fetchall()


    db.close()


    return jsonify({

        "users": [

            str(row[0])

            for row in rows

        ]

    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    init_database()


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
    print("=" * 60)


    app.run(

        host="0.0.0.0",

        port=port
    )