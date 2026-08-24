import os,secrets,time
from urllib.parse import urlencode
import aiohttp
from aiohttp import web
import database
API='https://discord.com/api/v10'; CLIENT_ID=CLIENT_SECRET=PUBLIC_URL=''; PORT=8080; RUNNER=None

def init_oauth():
 global CLIENT_ID,CLIENT_SECRET,PUBLIC_URL,PORT
 CLIENT_ID=os.getenv('DISCORD_CLIENT_ID','').strip(); CLIENT_SECRET=os.getenv('DISCORD_CLIENT_SECRET','').strip(); PUBLIC_URL=os.getenv('PUBLIC_URL','').rstrip('/'); PORT=int(os.getenv('PORT') or os.getenv('OAUTH_PORT','8080'))
 missing=[n for n,v in [('DISCORD_CLIENT_ID',CLIENT_ID),('DISCORD_CLIENT_SECRET',CLIENT_SECRET),('PUBLIC_URL',PUBLIC_URL)] if not v]
 if missing: raise RuntimeError('Missing environment variables: '+', '.join(missing))
 database.init_db()
def redirect_uri(): return PUBLIC_URL+'/oauth/callback'
def create_authorization_url(uid):
 state=secrets.token_urlsafe(48); database.create_oauth_state(state,str(uid))
 return 'https://discord.com/oauth2/authorize?'+urlencode({'client_id':CLIENT_ID,'response_type':'code','redirect_uri':redirect_uri(),'scope':'identify applications.commands','state':state,'prompt':'consent'})
async def exchange(code):
 async with aiohttp.ClientSession() as s:
  async with s.post(API+'/oauth2/token',data={'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'grant_type':'authorization_code','code':code,'redirect_uri':redirect_uri()}) as r:
   body=await r.text()
   if r.status!=200: print(f'[OAUTH] token exchange HTTP={r.status} body={body[:1000]}'); raise RuntimeError('OAuth token exchange failed')
   return await r.json()
async def me(token):
 async with aiohttp.ClientSession() as s:
  async with s.get(API+'/users/@me',headers={'Authorization':'Bearer '+token}) as r:
   body=await r.text()
   if r.status!=200: print(f'[OAUTH] /users/@me HTTP={r.status} body={body[:1000]}'); raise RuntimeError('OAuth user verification failed')
   return await r.json()
async def callback(request):
 state=request.query.get('state'); code=request.query.get('code'); error=request.query.get('error')
 if error:return web.Response(status=400,text='Authorization failed: '+error)
 if not state or not code:return web.Response(status=400,text='Missing OAuth state or code.')
 uid=database.consume_oauth_state(state)
 if uid is None:return web.Response(status=400,text='Invalid or expired OAuth state. Start /auto_join on again.')
 try:
  t=await exchange(code); access=t.get('access_token')
  if not access: raise RuntimeError('No OAuth access token returned')
  u=await me(access); returned=str(u.get('id'))
  if returned!=uid:return web.Response(status=403,text='The authorized Discord account does not match the account that started Auto Join.')
  expires=time.time()+int(t['expires_in']) if t.get('expires_in') is not None else None
  database.save_oauth_user(uid,access,t.get('refresh_token'),expires,t.get('token_type'),t.get('scope'))
  database.set_auto_join(uid,True)
  print(f'[OAUTH] User App authorization successful user={uid}')
  return web.Response(text='✅ Giveaway Tracker has been added to your Discord User Apps. Auto Join is now enabled. You can close this page.')
 except Exception as e:
  print(f'[OAUTH] Authorization failed user={uid}: {e}'); return web.Response(status=500,text='OAuth failed. Check the bot console.')
async def health(request): return web.Response(text='Giveaway Tracker OAuth server is online.')
async def start_oauth_server():
 global RUNNER
 if RUNNER:return
 app=web.Application(); app.router.add_get('/',health); app.router.add_get('/oauth/callback',callback); RUNNER=web.AppRunner(app); await RUNNER.setup(); site=web.TCPSite(RUNNER,'0.0.0.0',PORT); await site.start(); print(f'[OAUTH] Listening on port {PORT}'); print(f'[OAUTH] Redirect URI: {redirect_uri()}')
