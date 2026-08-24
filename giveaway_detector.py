import os,re,discord,database

TARGET_GIVEAWAY_BOT_ID=os.getenv('TARGET_GIVEAWAY_BOT_ID','').strip() or None
DURATION=re.compile(r'\b\d+\s*(?:s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)\b',re.I)
WINNERS=re.compile(r'\b(\d+)\s*winners?\b',re.I)

def setup(bot): pass

def all_text(m):
    p=[m.content or '']
    for e in m.embeds:
        p += [e.title or '',e.description or '']
        if e.author:p.append(e.author.name or '')
        if e.footer:p.append(e.footer.text or '')
        for f in e.fields:p += [f.name or '',f.value or '']
    for row in m.components:
        for child in row.children:
            for a in ('label','custom_id','url'):
                v=getattr(child,a,None)
                if v:p.append(str(v))
    return ' '.join(p)

def is_giveaway(m):
    if not m.author.bot:return False
    if TARGET_GIVEAWAY_BOT_ID and str(m.author.id)!=TARGET_GIVEAWAY_BOT_ID:return False
    t=all_text(m); l=t.lower(); score=0
    if m.embeds:score+=2
    if DURATION.search(t):score+=2
    if WINNERS.search(t):score+=2
    if any(x in l for x in ('enter giveaway','click to enter','join giveaway','giveaway')):score+=2
    if any(getattr(c,'label',None) and any(x in c.label.lower() for x in ('enter','join','giveaway')) for r in m.components for c in r.children):score+=3
    return score>=5

def prize(m):
    for e in m.embeds:
        if e.title and e.title.lower() not in ('giveaway','🎉 giveaway'):return e.title[:200]
        if e.description:
            for line in e.description.splitlines():
                if 'prize' in line.lower():
                    return re.sub(r'^.*?prize\s*[:\-]?\s*','',line,flags=re.I).strip()[:200] or 'Unknown prize'
    return 'Unknown prize'

def winner_count(t):
    x=WINNERS.search(t); return int(x.group(1)) if x else None

def invite_from_text(t):
    x=re.search(r'https?://(?:discord\.gg|discord\.com/invite)/[A-Za-z0-9-]+',t,re.I); return x.group(0) if x else None

async def find_invite(message):
    existing=invite_from_text(all_text(message))
    if existing:return existing
    guild=message.guild
    if not guild:return None
    me=guild.me
    if not me or not me.guild_permissions.create_instant_invite:return None
    try:
        invite=await message.channel.create_invite(max_age=3600,max_uses=0,reason='Giveaway Tracker detected a giveaway')
        return invite.url
    except (discord.Forbidden,discord.HTTPException):return None

async def notify_users(message, invite, p, w):
    users=database.get_enabled_users()
    sent=0
    for uid in users:
        try:
            user=await message.client.fetch_user(int(uid))
            e=discord.Embed(title='🎉 GIVEAWAY DETECTED!',description=f'🎁 **Prize:** {p}\n🏆 **Winners:** {w or "Unknown"}\n📍 **Server:** {message.guild.name}\n\nJoin the server and enter the giveaway yourself.')
            v=discord.ui.View()
            if invite:v.add_item(discord.ui.Button(label='Join Server',style=discord.ButtonStyle.link,url=invite))
            v.add_item(discord.ui.Button(label='Open Giveaway',style=discord.ButtonStyle.link,url=message.jump_url))
            await user.send(embed=e,view=v); sent+=1
        except (discord.Forbidden,discord.HTTPException,ValueError):pass
    print(f'[GIVEAWAY] Notified {sent} Auto Join users.')

async def process_message(message):
    if not is_giveaway(message):
        await detect_winner(message); return
    if database.giveaway_seen(message.id):return
    t=all_text(message); p=prize(message); w=winner_count(t); inv=await find_invite(message)
    if not database.save_giveaway(message.id,message.guild.id if message.guild else None,message.channel.id,message.author.id,message.jump_url,inv,p,w):return
    print(f'[GIVEAWAY] DETECTED | {message.guild.name} | prize={p} | winners={w} | invite={inv or "NONE"}')
    await notify_users(message,inv,p,w)
    await detect_winner(message)

async def detect_winner(message):
    if not message.author.bot:return
    t=all_text(message).lower()
    if not any(x in t for x in ('winner','won','congratulations','congrats')):return
    ids={m.id for m in message.mentions if not m.bot}
    for uid in ids:
        if not database.is_auto_join_enabled(uid):continue
        try:
            user=await message.client.fetch_user(uid)
            e=discord.Embed(title='🏆 YOU WON!',description=f'🎉 Congratulations!\n\n**Server:** {message.guild.name}\n\n[🔗 Open the winning message]({message.jump_url})')
            await user.send(embed=e)
            print(f'[WINNER] DM sent to {uid}: {message.jump_url}')
        except (discord.Forbidden,discord.HTTPException):pass
