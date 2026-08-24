# oauth_server.py

import os
import secrets
import time
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

import database


# =========================================================
# CONFIG
# =========================================================

DISCORD_API = "https://discord.com/api/v10"

STATE_EXPIRE_SECONDS = 10 * 60

CLIENT_ID = None
CLIENT_SECRET = None
PUBLIC_URL = None
PORT = None

_runner = None
_site = None


# =========================================================
# INITIALIZE OAUTH
# =========================================================

def init_oauth():
    global CLIENT_ID
    global CLIENT_SECRET
    global PUBLIC_URL
    global PORT

    CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()
    CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
    PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")

    # Render gives us PORT automatically.
    # Local computers can use OAUTH_PORT.
    PORT = int(
        os.getenv("PORT")
        or os.getenv("OAUTH_PORT", "8080")
    )

    missing = []

    if not CLIENT_ID:
        missing.append("DISCORD_CLIENT_ID")

    if not CLIENT_SECRET:
        missing.append("DISCORD_CLIENT_SECRET")

    if not PUBLIC_URL:
        missing.append("PUBLIC_URL")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )

    database.init_db()

    print("[OAUTH] OAuth initialized.")
    print(
        f"[OAUTH] Redirect URI: {redirect_uri()}"
    )


# =========================================================
# REDIRECT URI
# =========================================================

def redirect_uri():
    return f"{PUBLIC_URL}/oauth/callback"


# =========================================================
# CREATE USER INSTALL URL
# =========================================================

def create_authorization_url(user_id: str) -> str:

    user_id = str(user_id)

    # -----------------------------------------------------
    # Secure random state
    # -----------------------------------------------------

    state = secrets.token_urlsafe(48)

    # Save state in database.
    database.create_oauth_state(
        state=state,
        user_id=user_id
    )

    # -----------------------------------------------------
    # DISCORD USER INSTALL
    # -----------------------------------------------------
    #
    # IMPORTANT:
    #
    # integration_type=1
    #
    # means USER INSTALL.
    #
    # This is what we want:
    #
    #     Add to My Apps
    #
    # NOT:
    #
    #     Add to Server
    #
    # -----------------------------------------------------

    params = {
        "client_id": CLIENT_ID,

        "response_type": "code",

        "redirect_uri": redirect_uri(),

        # User App scopes.
        #
        # DO NOT add:
        # bot
        # guilds.join
        #
        "scope": "identify applications.commands",

        "state": state,

        # 1 = User Install
        "integration_type": "1",

        # Always show authorization.
        "prompt": "consent",
    }

    url = (
        "https://discord.com/oauth2/authorize?"
        + urlencode(params)
    )

    print(
        f"[OAUTH] Created User Install authorization "
        f"for user={user_id}"
    )

    return url


# =========================================================
# EXCHANGE CODE FOR TOKEN
# =========================================================

async def exchange_code(code: str):

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,

        "grant_type": "authorization_code",

        "code": code,

        "redirect_uri": redirect_uri(),
    }

    async with aiohttp.ClientSession() as session:

        async with session.post(
            f"{DISCORD_API}/oauth2/token",
            data=data
        ) as response:

            body = await response.text()

            if response.status != 200:

                print(
                    "[OAUTH] Token exchange failed"
                )

                print(
                    f"[OAUTH] HTTP {response.status}"
                )

                print(
                    f"[OAUTH] Response: {body[:1000]}"
                )

                raise RuntimeError(
                    "OAuth token exchange failed."
                )

            return await response.json()


# =========================================================
# GET DISCORD USER
# =========================================================

async def get_discord_user(
    access_token: str
):

    headers = {
        "Authorization":
            f"Bearer {access_token}"
    }

    async with aiohttp.ClientSession() as session:

        async with session.get(
            f"{DISCORD_API}/users/@me",
            headers=headers
        ) as response:

            body = await response.text()

            if response.status == 401:

                print(
                    "[OAUTH] OAuth token is expired "
                    "or invalid."
                )

                raise RuntimeError(
                    "OAuth token expired or invalid."
                )

            if response.status != 200:

                print(
                    "[OAUTH] /users/@me failed"
                )

                print(
                    f"[OAUTH] HTTP {response.status}"
                )

                print(
                    f"[OAUTH] Response: {body[:1000]}"
                )

                raise RuntimeError(
                    "Discord user verification failed."
                )

            return await response.json()


# =========================================================
# OAUTH CALLBACK
# =========================================================

async def oauth_callback(
    request: web.Request
):

    state = request.query.get("state")
    code = request.query.get("code")
    error = request.query.get("error")

    # -----------------------------------------------------
    # User denied authorization
    # -----------------------------------------------------

    if error:

        print(
            f"[OAUTH] Discord authorization failed: "
            f"{error}"
        )

        return web.Response(
            status=400,
            text=(
                "❌ Authorization was cancelled."
            )
        )

    # -----------------------------------------------------
    # Missing parameters
    # -----------------------------------------------------

    if not state or not code:

        return web.Response(
            status=400,
            text=(
                "❌ Missing OAuth state or authorization code."
            )
        )

    # -----------------------------------------------------
    # Validate + consume state
    # -----------------------------------------------------
    #
    # consume_oauth_state() must:
    #
    # 1. Find the state
    # 2. Check expiration
    # 3. Check it wasn't already used
    # 4. Mark it used
    #
    # -----------------------------------------------------

    expected_user_id = database.consume_oauth_state(
        state
    )

    if expected_user_id is None:

        print(
            "[OAUTH] Invalid, expired, "
            "or already-used OAuth state."
        )

        return web.Response(
            status=400,
            text=(
                "❌ Invalid OAuth state.\n\n"
                "Please run `/auto_join on` again "
                "to generate a new authorization."
            )
        )

    expected_user_id = str(
        expected_user_id
    )

    try:

        # -------------------------------------------------
        # Exchange authorization code
        # -------------------------------------------------

        token_data = await exchange_code(
            code
        )

        access_token = token_data.get(
            "access_token"
        )

        refresh_token = token_data.get(
            "refresh_token"
        )

        expires_in = token_data.get(
            "expires_in"
        )

        token_type = token_data.get(
            "token_type"
        )

        scope = token_data.get(
            "scope"
        )

        if not access_token:

            raise RuntimeError(
                "Discord did not return an OAuth access token."
            )

        # -------------------------------------------------
        # Verify Discord account
        # -------------------------------------------------

        discord_user = await get_discord_user(
            access_token
        )

        returned_user_id = str(
            discord_user.get("id")
        )

        # -------------------------------------------------
        # VERY IMPORTANT SECURITY CHECK
        # -------------------------------------------------

        if returned_user_id != expected_user_id:

            print(
                "[OAUTH] User ID mismatch."
            )

            print(
                f"[OAUTH] Expected user: "
                f"{expected_user_id}"
            )

            print(
                f"[OAUTH] Returned user: "
                f"{returned_user_id}"
            )

            return web.Response(
                status=403,
                text=(
                    "❌ The Discord account you "
                    "authorized does not match "
                    "the account that started "
                    "Auto Join."
                )
            )

        # -------------------------------------------------
        # Calculate expiration
        # -------------------------------------------------

        expires_at = None

        if expires_in is not None:

            try:

                expires_at = (
                    time.time()
                    + int(expires_in)
                )

            except (
                TypeError,
                ValueError
            ):

                expires_at = None

        # -------------------------------------------------
        # SAVE USER AUTHORIZATION
        # -------------------------------------------------
        #
        # This is the important part.
        #
        # Once this exists:
        #
        # /auto_join on
        #
        # will NOT ask the user to authenticate again.
        #
        # -------------------------------------------------

        database.save_oauth_user(
            user_id=expected_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            token_type=token_type,
            scope=scope,
        )

        # -------------------------------------------------
        # ENABLE AUTO JOIN
        # -------------------------------------------------

        database.set_auto_join(
            expected_user_id,
            True
        )

        print(
            "[OAUTH] User App authorization successful "
            f"for user={expected_user_id}"
        )

        # -------------------------------------------------
        # SUCCESS PAGE
        # -------------------------------------------------

        return web.Response(
            status=200,
            content_type="text/html",
            text="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Giveaway Tracker</title>

    <style>
        body {
            margin: 0;
            background: #111827;
            color: white;
            font-family: Arial, sans-serif;

            display: flex;
            align-items: center;
            justify-content: center;

            min-height: 100vh;
        }

        .box {
            width: 90%;
            max-width: 520px;

            background: #1f2937;

            padding: 40px;

            border-radius: 20px;

            text-align: center;

            box-shadow:
                0 20px 60px
                rgba(0, 0, 0, 0.4);
        }

        .icon {
            font-size: 60px;
            margin-bottom: 20px;
        }

        h1 {
            margin-bottom: 10px;
        }

        p {
            color: #d1d5db;
            line-height: 1.6;
        }

        .success {
            color: #4ade80;
        }
    </style>
</head>

<body>

<div class="box">

    <div class="icon">
        🎉
    </div>

    <h1 class="success">
        Giveaway Tracker Authorized!
    </h1>

    <p>
        Giveaway Tracker has been added
        to your Discord User Apps.
    </p>

    <p>
        <strong>
            Auto Join is now enabled.
        </strong>
    </p>

    <p>
        You can safely close this page.
    </p>

</div>

</body>
</html>
"""
        )

    except Exception as exc:

        # Never print tokens.
        print(
            "[OAUTH] Authorization failed:"
            f" {type(exc).__name__}: {exc}"
        )

        return web.Response(
            status=500,
            text=(
                "❌ OAuth authorization failed.\n\n"
                "Please try `/auto_join on` again."
            )
        )


# =========================================================
# HEALTH CHECK
# =========================================================

async def health(
    request: web.Request
):

    return web.Response(
        status=200,
        text=(
            "Giveaway Tracker OAuth server is online."
        )
    )


# =========================================================
# START SERVER
# =========================================================

async def start_oauth_server():

    global _runner
    global _site

    # Don't start it twice.
    if _runner is not None:
        return

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/oauth/callback",
        oauth_callback
    )

    _runner = web.AppRunner(
        app
    )

    await _runner.setup()

    _site = web.TCPSite(
        _runner,
        host="0.0.0.0",
        port=PORT
    )

    await _site.start()

    print(
        f"[OAUTH] Server started on port {PORT}"
    )

    print(
        f"[OAUTH] Callback: {redirect_uri()}"
    )