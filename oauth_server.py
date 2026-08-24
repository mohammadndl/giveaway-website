import os
import secrets
import time
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

import database


DISCORD_API = "https://discord.com/api/v10"

STATE_TTL = 600

CLIENT_ID = ""
CLIENT_SECRET = ""
PUBLIC_URL = ""
PORT = 8080

_runner = None
_site = None


def init_oauth():
    global CLIENT_ID
    global CLIENT_SECRET
    global PUBLIC_URL
    global PORT

    CLIENT_ID = os.getenv(
        "DISCORD_CLIENT_ID",
        ""
    ).strip()

    CLIENT_SECRET = os.getenv(
        "DISCORD_CLIENT_SECRET",
        ""
    ).strip()

    PUBLIC_URL = os.getenv(
        "PUBLIC_URL",
        ""
    ).strip().rstrip("/")

    PORT = int(
        os.getenv("PORT")
        or os.getenv("OAUTH_PORT", "8080")
    )

    if not CLIENT_ID:
        raise RuntimeError(
            "DISCORD_CLIENT_ID is missing."
        )

    if not CLIENT_SECRET:
        raise RuntimeError(
            "DISCORD_CLIENT_SECRET is missing."
        )

    if not PUBLIC_URL:
        raise RuntimeError(
            "PUBLIC_URL is missing."
        )

    database.init_db()

    print(
        "[OAUTH] Initialized"
    )

    print(
        f"[OAUTH] Callback: {redirect_uri()}"
    )


def redirect_uri():
    return (
        f"{PUBLIC_URL}/oauth/callback"
    )


def create_authorization_url(
    user_id
):
    user_id = str(user_id)

    state = secrets.token_urlsafe(48)

    # IMPORTANT:
    # positional arguments match database.py exactly.
    database.create_oauth_state(
        state,
        user_id
    )

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri(),

        # User Install.
        "scope": "identify applications.commands",

        "state": state,

        # Discord User Install.
        "integration_type": "1",

        "prompt": "consent"
    }

    return (
        "https://discord.com/oauth2/authorize?"
        + urlencode(params)
    )


async def exchange_code(code):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri()
    }

    async with aiohttp.ClientSession() as session:

        async with session.post(
            f"{DISCORD_API}/oauth2/token",
            data=data
        ) as response:

            body = await response.text()

            if response.status != 200:

                print(
                    f"[OAUTH] Token HTTP "
                    f"{response.status}"
                )

                print(
                    f"[OAUTH] Response: "
                    f"{body[:1000]}"
                )

                raise RuntimeError(
                    "OAuth token exchange failed."
                )

            return await response.json()


async def get_discord_user(
    access_token
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

                raise RuntimeError(
                    "OAuth token expired or invalid."
                )

            if response.status != 200:

                print(
                    f"[OAUTH] User lookup HTTP "
                    f"{response.status}"
                )

                print(
                    f"[OAUTH] Response: "
                    f"{body[:1000]}"
                )

                raise RuntimeError(
                    "Discord user lookup failed."
                )

            return await response.json()


async def oauth_callback(request):
    state = request.query.get("state")
    code = request.query.get("code")
    error = request.query.get("error")

    if error:
        return web.Response(
            status=400,
            text="Authorization was cancelled."
        )

    if not state or not code:
        return web.Response(
            status=400,
            text="Invalid OAuth request."
        )

    expected_user_id = (
        database.consume_oauth_state(
            state,
            STATE_TTL
        )
    )

    if expected_user_id is None:

        print(
            "[OAUTH] Invalid or expired state."
        )

        return web.Response(
            status=400,
            text=(
                "Invalid OAuth state. "
                "Run /auto_join on again."
            )
        )

    try:

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
                "No OAuth access token returned."
            )

        discord_user = (
            await get_discord_user(
                access_token
            )
        )

        returned_user_id = str(
            discord_user["id"]
        )

        if returned_user_id != str(
            expected_user_id
        ):

            print(
                "[OAUTH] User ID mismatch."
            )

            return web.Response(
                status=403,
                text=(
                    "The authorized Discord "
                    "account does not match."
                )
            )

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

        database.save_oauth_user(
            user_id=expected_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            token_type=token_type,
            scope=scope
        )

        database.set_auto_join(
            expected_user_id,
            True
        )

        print(
            f"[OAUTH] User App authorized: "
            f"{expected_user_id}"
        )

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
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #111827;
    color: white;
    font-family: Arial, sans-serif;
}
.box {
    width: 90%;
    max-width: 520px;
    padding: 40px;
    text-align: center;
    border-radius: 20px;
    background: #1f2937;
    box-shadow: 0 20px 60px rgba(0,0,0,.4);
}
.icon {
    font-size: 64px;
}
h1 {
    color: #4ade80;
}
p {
    color: #d1d5db;
    line-height: 1.6;
}
</style>
</head>
<body>
<div class="box">
<div class="icon">🎉</div>
<h1>Giveaway Tracker Authorized!</h1>
<p>
Giveaway Tracker has been added to
your Discord User Apps.
</p>
<p>
<strong>Auto Join is now enabled.</strong>
</p>
<p>
You can close this page.
</p>
</div>
</body>
</html>
"""
        )

    except Exception as exc:

        print(
            f"[OAUTH ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        return web.Response(
            status=500,
            text=(
                "OAuth authorization failed."
            )
        )


async def health(request):
    return web.Response(
        text="Giveaway Tracker OAuth server is online."
    )


async def start_oauth_server():

    global _runner
    global _site

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

    _runner = web.AppRunner(app)

    await _runner.setup()

    _site = web.TCPSite(
        _runner,
        "0.0.0.0",
        PORT
    )

    await _site.start()

    print(
        f"[OAUTH] Server listening on {PORT}"
    )