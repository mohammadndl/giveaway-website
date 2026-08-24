import os,re,discord,database
TARGET_GIVEAWAY_BOT_ID=os.getenv('TARGET_GIVEAWAY_BOT_ID','').strip() or None
DURATION=re.compile(r'\b\d+\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b',re.I); WINNER=re.compile(r'\b\d*\s*winner(?:s)?\b',re.I); ENTRY=re.compile(r'\b(?:\d[\d,]*\s*(?:entries|participants)|participants?\s*[:\-]?\s*\d[\d,]*)\b',re.I)
def configure_target_bot(x):
 global TARGET_GIVEAWAY_BOT_ID; TARGET_GIVEAWAY_BOT_ID=str(x).strip() if x else None
def score(m):
 text=m.content+' '+' '.join((e.title or '')+' '+(e.description or '') for e in m.embeds)+' '+' '.join(str(getattr(c,a,'')) for row in m.components for c in row.children for a in ('label','custom_id','url'))
 s=2 if m.embeds else 0; reasons=['embed'] if m.embeds else []
 if m.components and any(x in text.lower() for x in ('enter','join','giveaway','participate')):s+=2;reasons.append('button')
 for rx,name,pts in ((DURATION,'duration',2),(WINNER,'winner',2),(ENTRY,'participants',2)):
  if rx.search(text):s+=pts;reasons.append(name)
 if any(x in text.lower() for x in ('ends in','ending in','time remaining','click to enter','react to enter')):s+=2;reasons.append('timing')
 return s,reasons
async def process_message(m):
 if not m.author.bot or (TARGET_GIVEAWAY_BOT_ID and str(m.author.id)!=TARGET_GIVEAWAY_BOT_ID) or database.giveaway_already_detected(m.id):return False
 s,r=score(m)
 if s<4:return False
 if database.mark_giveaway_detected(m.id,str(m.guild.id) if m.guild else None,str(m.channel.id),str(m.author.id)):
  print(f'[DETECTOR] Giveaway detected message={m.id} score={s} signals={", ".join(r)}');return True
 return False
