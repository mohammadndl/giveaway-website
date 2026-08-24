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
OAUTH_PORT = 8080
_runner = None
_site = None


def init_oauth() -> None:
    global CLIENT_ID, CLIENT_SECRET, PUBLIC_URL, OAUTH_PORT
    CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
    PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
    OAUTH_PORT = int(os.getenv("OAUTH_PORT") or os.getenv("PORT") or "8080")
    missing = [k for k, v in {
        "DISCORD_CLIENT_ID": CLIENT_ID,
        "DISCORD_CLIENT_SECRET": CLIENT_SECRET,
        "PUBLIC_URL": PUBLIC_URL,
    }.items() if not v]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))
    database.init_db()


def redirect_uri() -> str:
    return f"{PUBLIC_URL}/oauth/callback"


def create_authorization_url(user_id: str) -> str:
    state = secrets.token_urlsafe(48)
    database.create_oauth_state(state, str(user_id))
    # integration_type=1 is Discord's USER_INSTALL integration type.
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri(),
        "scope": "identify applications.commands",
        "state": state,
        "integration_type": "1",
        "prompt": "consent",
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)


async def exchange_code(code: str) -> dict:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{DISCORD_API}/oauth2/token", data=data) as response:
            body = await response.text()
            if response.status != 200:
                print(f"[OAUTH] Token exchange failed: HTTP {response.status}; body={body[:2000]}")
                raise RuntimeError("Discord rejected the OAuth code.")
            return await response.json()


async def get_discord_user(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API}/users/@me", headers=headers) as response:
            body = await response.text()
            if response.status == 401:
                raise RuntimeError("OAuth access token is expired or invalid.")
            if response.status != 200:
                print(f"[OAUTH] /users/@me failed: HTTP {response.status}; body={body[:2000]}")
                raise RuntimeError("Discord user verification failed.")
            return await response.json()


async def oauth_callback(request: web.Request) -> web.Response:
    state = request.query.get("state")
    code = request.query.get("code")
    error = request.query.get("error")

    if error:
        return web.Response(status=400, text=f"Authorization failed: {error}")
    if not state or not code:
        return web.Response(status=400, text="Missing OAuth state or code.")

    stored = database.get_oauth_state(state)
    if not stored:
        return web.Response(status=400, text="Invalid OAuth state.")
    if stored["used"]:
        return web.Response(status=400, text="This authorization has already been used.")
    if time.time() - float(stored["created_at"]) > STATE_TTL:
        database.mark_oauth_state_used(state)
        return web.Response(status=400, text="OAuth authorization expired. Run /auto_join on again.")
    if not database.mark_oauth_state_used(state):
        return web.Response(status=400, text="This authorization has already been used.")

    expected_user_id = str(stored["user_id"])

    try:
        token_data = await exchange_code(code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("Discord returned no access token.")

        user = await get_discord_user(access_token)
        returned_user_id = str(user.get("id", ""))
        if returned_user_id != expected_user_id:
            return web.Response(status=403, text="The authorized Discord account does not match the account that started /auto_join.")

        expires_in = token_data.get("expires_in")
        expires_at = time.time() + int(expires_in) if expires_in else None

        database.save_oauth_user(
            expected_user_id,
            access_token,
            token_data.get("refresh_token"),
            expires_at,
            token_data.get("token_type"),
            token_data.get("scope"),
        )
        database.set_auto_join(expected_user_id, True)

        print(f"[OAUTH] User Install authorization succeeded for user {expected_user_id}")
        return web.Response(
            status=200,
            text="✅ Giveaway Tracker has been added to your Discord User Apps. Auto Join is now enabled. You can close this page.",
        )
    except Exception as exc:
        print(f"[OAUTH] Authorization failed for user {expected_user_id}: {exc}")
        return web.Response(status=500, text="OAuth authorization failed. Check the bot console for the server-side error.")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="Giveaway Tracker OAuth server is online.")


async def start_oauth_server() -> None:
    global _runner, _site
    if _runner is not None:
        return
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/oauth/callback", oauth_callback)
    _runner = web.AppRunner(app)
    await _runner.setup()
    _site = web.TCPSite(_runner, "0.0.0.0", OAUTH_PORT)
    await _site.start()
    print(f"[OAUTH] Listening on port {OAUTH_PORT}")
    print(f"[OAUTH] Redirect URI: {redirect_uri()}")
