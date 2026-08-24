# giveaway_detector.py

import os
import re

import discord

import database


TARGET_GIVEAWAY_BOT_ID = (
    os.getenv(
        "TARGET_GIVEAWAY_BOT_ID",
        ""
    ).strip()
    or None
)


DURATION_RE = re.compile(
    r"\b\d+\s*"
    r"(?:seconds?|secs?|s|"
    r"minutes?|mins?|m|"
    r"hours?|hrs?|h|"
    r"days?|d)\b",
    re.I
)


WINNER_RE = re.compile(
    r"\b\d*\s*winner(?:s)?\b",
    re.I
)


ENTRY_RE = re.compile(
    r"\b(?:"
    r"\d[\d,]*\s*(?:entries|participants)"
    r"|participants?\s*[:\-]?\s*\d[\d,]*"
    r")\b",
    re.I
)


def configure_target_bot(
    bot_id
):

    global TARGET_GIVEAWAY_BOT_ID

    TARGET_GIVEAWAY_BOT_ID = (
        str(bot_id).strip()
        if bot_id
        else None
    )


def embed_text(
    embed: discord.Embed
):

    parts = [

        embed.title or "",

        embed.description or "",

        (
            embed.footer.text
            if embed.footer
            else ""
        ),

        (
            embed.author.name
            if embed.author
            else ""
        ),
    ]

    for field in embed.fields:

        parts.append(
            field.name or ""
        )

        parts.append(
            field.value or ""
        )

    return " ".join(parts)


def component_text(
    message: discord.Message
):

    parts = []

    for row in message.components:

        for child in row.children:

            for attr in (
                "label",
                "custom_id",
                "url"
            ):

                value = getattr(
                    child,
                    attr,
                    None
                )

                if value:

                    parts.append(
                        str(value)
                    )

    return " ".join(parts)


def score_giveaway(
    message: discord.Message
):

    text = []

    text.append(
        message.content or ""
    )

    for embed in message.embeds:

        text.append(
            embed_text(embed)
        )

    text.append(
        component_text(message)
    )

    combined = " ".join(text)

    lower = combined.lower()

    score = 0

    reasons = []

    if message.embeds:

        score += 2

        reasons.append(
            "embed"
        )

    components = (
        component_text(message)
    )

    if components:

        component_lower = (
            components.lower()
        )

        if any(
            x in component_lower
            for x in (
                "enter",
                "join",
                "participate",
                "giveaway",
                "claim"
            )
        ):

            score += 2

            reasons.append(
                "giveaway button"
            )

    if DURATION_RE.search(
        combined
    ):

        score += 2

        reasons.append(
            "duration"
        )

    if WINNER_RE.search(
        combined
    ):

        score += 2

        reasons.append(
            "winner count"
        )

    if ENTRY_RE.search(
        combined
    ):

        score += 2

        reasons.append(
            "participant count"
        )

    structural = (

        "ends in",

        "ending in",

        "time remaining",

        "click to enter",

        "react to enter",

        "entries",

        "participants",

        "winner",
    )

    hits = sum(
        1
        for phrase in structural
        if phrase in lower
    )

    if hits:

        score += min(
            hits,
            3
        )

        reasons.append(
            f"metadata={hits}"
        )

    return score, reasons


async def process_message(
    message: discord.Message
):

    if not message.author.bot:

        return False

    if (
        TARGET_GIVEAWAY_BOT_ID
        and
        str(message.author.id)
        != TARGET_GIVEAWAY_BOT_ID
    ):

        return False

    if database.giveaway_already_detected(
        str(message.id)
    ):

        return False

    score, reasons = (
        score_giveaway(message)
    )

    if score < 4:

        return False

    saved = (
        database.mark_giveaway_detected(
            str(message.id),

            (
                str(message.guild.id)
                if message.guild
                else None
            ),

            str(message.channel.id),

            str(message.author.id)
        )
    )

    if saved:

        print(
            "[DETECTOR] Giveaway detected"
        )

        print(
            f"Message: {message.id}"
        )

        print(
            f"Score: {score}"
        )

        print(
            f"Signals: "
            f"{', '.join(reasons)}"
        )

        return True

    return False