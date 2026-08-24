import asyncio,time,random,re,discord
from discord import app_commands
BOT=None; ACTIVE={}; RX=re.compile(r'^(\d+)\s*([smhd])$',re.I)
def parse(v):
 m=RX.fullmatch(v.strip())
 return None if not m else int(m.group(1))*{'s':1,'m':60,'h':3600,'d':86400}[m.group(2).lower()]
def rem(x):
 x=max(0,int(x));d,x=divmod(x,86400);h,x=divmod(x,3600);m,s=divmod(x,60);return f'{d}d {h}h {m}m' if d else f'{h}h {m}m {s}s' if h else f'{m}m {s}s' if m else f'{s}s'
class G:
 def __init__(self,ch,host,prize,winners,end):self.channel_id=ch;self.host_id=host;self.prize=prize;self.winners=winners;self.end=end;self.message=None;self.users=set();self.ended=False
def embed(g):return discord.Embed(title='🎉 Giveaway Ended' if g.ended else '🎉 GIVEAWAY',description=f'## 🎁 {g.prize}\n\n⏳ **Time Left:** `{("ENDED" if g.ended else rem(g.end-time.time()))}`\n👥 **Participants:** `{len(g.users)}`\n🏆 **Winners:** `{g.winners}`').set_footer(text=f'Hosted by <@{g.host_id}>')
class V(discord.ui.View):
 def __init__(self,g,disabled=False):
  super().__init__(timeout=None);self.g=g
  a=discord.ui.Button(label='Enter Giveaway',style=discord.ButtonStyle.success,emoji='🎉',disabled=disabled);b=discord.ui.Button(label='Leave',style=discord.ButtonStyle.secondary,emoji='🚪',disabled=disabled);a.callback=self.enter;b.callback=self.leave;self.add_item(a);self.add_item(b)
 async def enter(self,i):
  if self.g.ended:return await i.response.send_message('❌ This giveaway has ended.',ephemeral=True)
  if i.user.id in self.g.users:return await i.response.send_message('ℹ️ You are already entered.',ephemeral=True)
  self.g.users.add(i.user.id);await i.response.send_message('🎉 You entered!',ephemeral=True);await update(self.g)
 async def leave(self,i):
  if self.g.ended:return await i.response.send_message('❌ This giveaway has ended.',ephemeral=True)
  if i.user.id not in self.g.users:return await i.response.send_message('ℹ️ You are not entered.',ephemeral=True)
  self.g.users.remove(i.user.id);await i.response.send_message('🚪 You left.',ephemeral=True);await update(self.g)
async def update(g):
 if not g.message:return
 try:await g.message.edit(embed=embed(g),view=V(g,g.ended))
 except discord.HTTPException:g.message=None
async def finish(g):
 g.ended=True;ACTIVE.pop(g.channel_id,None);w=list(g.users);random.shuffle(w);w=w[:g.winners];await update(g)
 try:c=await BOT.fetch_channel(g.channel_id)
 except discord.HTTPException:return
 await c.send(f'🎉 **Giveaway Ended!**\n🎁 Prize: **{g.prize}**\n'+('😢 No participants entered.' if not w else '🏆 Winners: '+', '.join(f'<@{x}>' for x in w)))
async def loop(g):
 while not g.ended:
  if time.time()>=g.end:return await finish(g)
  await update(g);await asyncio.sleep(1 if g.end-time.time()<=60 else 5)
@app_commands.command(name='giveaway',description='Create a giveaway.')
@app_commands.describe(prize='Prize',duration='30s, 10m, 2h, or 1d',winners='Winner count')
async def giveaway(i,prize:str,duration:str,winners:app_commands.Range[int,1,100]):
 if i.guild is None:return await i.response.send_message('❌ Use this in a server.',ephemeral=True)
 s=parse(duration)
 if not s:return await i.response.send_message('❌ Invalid duration.',ephemeral=True)
 await i.response.defer();g=G(i.channel_id,i.user.id,prize,int(winners),time.time()+s);g.message=await i.followup.send(embed=embed(g),view=V(g),wait=True);ACTIVE[g.channel_id]=g;asyncio.create_task(loop(g))
def setup(bot):
 global BOT;BOT=bot;bot.tree.add_command(giveaway)
