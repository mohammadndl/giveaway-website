import os
import re
from typing import Optional
import discord
import database

TARGET_GIVEAWAY_BOT_ID = os.getenv("TARGET_GIVEAWAY_BOT_ID", "").strip() or None
DURATION_RE = re.compile(r"\b\d+\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b", re.I)
WINNER_RE = re.compile(r"\b\d*\s*winner(?:s)?\b", re.I)
ENTRY_RE = re.compile(r"\b(?:\d[\d,]*\s*(?:entries|participants)|participants?\s*[:\-]?\s*\d[\d,]*)\b", re.I)


def embed_text(embed: discord.Embed) -> str:
    parts = [embed.title or "", embed.description or "", embed.footer.text if embed.footer else "", embed.author.name if embed.author else ""]
    for field in embed.fields:
        parts.extend([field.name or "", field.value or ""])
    return " ".join(parts)


def component_text(message: discord.Message) -> str:
    parts = []
    for row in message.components:
        for child in row.children:
            for attr in ("label", "custom_id", "url"):
                value = getattr(child, attr, None)
                if value:
                    parts.append(str(value))
    return " ".join(parts)


def score_giveaway(message: discord.Message):
    score = 0
    reasons = []
    text = " ".join([message.content or "", *(embed_text(e) for e in message.embeds), component_text(message)])
    lower = text.lower()

    if message.embeds:
        score += 2; reasons.append("embed")
    if message.components and any(x in component_text(message).lower() for x in ("enter", "join", "participate", "claim")):
        score += 2; reasons.append("giveaway button/component")
    if DURATION_RE.search(text):
        score += 2; reasons.append("duration/countdown")
    if WINNER_RE.search(text):
        score += 2; reasons.append("winner information")
    if ENTRY_RE.search(text):
        score += 2; reasons.append("participant/entry information")

    structural = ("ends in", "ending in", "time remaining", "entries", "participants", "winner", "click to enter", "react to enter")
    hits = sum(1 for x in structural if x in lower)
    if hits:
        score += min(hits, 3); reasons.append(f"metadata signals={hits}")
    return score, reasons


def configure_target_bot(bot_id: Optional[str]):
    global TARGET_GIVEAWAY_BOT_ID
    TARGET_GIVEAWAY_BOT_ID = str(bot_id).strip() if bot_id else None


async def process_message(message: discord.Message) -> bool:
    if not message.author.bot:
        return False
    if TARGET_GIVEAWAY_BOT_ID and str(message.author.id) != TARGET_GIVEAWAY_BOT_ID:
        return False
    if database.giveaway_already_detected(str(message.id)):
        return False

    score, reasons = score_giveaway(message)
    if score < 4:
        return False

    if database.save_detected_giveaway(
        str(message.id),
        str(message.guild.id) if message.guild else None,
        str(message.channel.id),
        str(message.author.id),
    ):
        print(f"[DETECTOR] Giveaway detected | message={message.id} | author={message.author} | score={score} | signals={', '.join(reasons)}")
        return True
    return False
