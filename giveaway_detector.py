import os
import re

import discord

import database
import auto_join


TARGET_GIVEAWAY_BOT_ID = (
    os.getenv(
        "TARGET_GIVEAWAY_BOT_ID",
        ""
    ).strip()
    or None
)


def setup(bot):
    print(
        "[DETECTOR] Started."
    )

    print(
        "[DETECTOR] Target bot: "
        + (
            TARGET_GIVEAWAY_BOT_ID
            if TARGET_GIVEAWAY_BOT_ID
            else "ALL BOTS"
        )
    )


def collect_text(
    message: discord.Message
) -> str:

    parts = []

    if message.content:
        parts.append(
            message.content
        )

    for embed in message.embeds:

        if embed.title:
            parts.append(
                embed.title
            )

        if embed.description:
            parts.append(
                embed.description
            )

        if embed.author:
            if embed.author.name:
                parts.append(
                    embed.author.name
                )

        if embed.footer:
            if embed.footer.text:
                parts.append(
                    embed.footer.text
                )

        for field in embed.fields:

            parts.append(
                field.name or ""
            )

            parts.append(
                field.value or ""
            )

    for row in message.components:

        for component in row.children:

            label = getattr(
                component,
                "label",
                None
            )

            custom_id = getattr(
                component,
                "custom_id",
                None
            )

            url = getattr(
                component,
                "url",
                None
            )

            if label:
                parts.append(
                    str(label)
                )

            if custom_id:
                parts.append(
                    str(custom_id)
                )

            if url:
                parts.append(
                    str(url)
                )

    return " ".join(parts)


def has_duration(text: str) -> bool:

    return bool(
        re.search(
            r"\b\d+\s*"
            r"(?:s|sec|secs|second|seconds|"
            r"m|min|mins|minute|minutes|"
            r"h|hr|hrs|hour|hours|"
            r"d|day|days)\b",
            text,
            re.IGNORECASE
        )
    )


def get_winner_count(
    text: str
):

    patterns = [
        r"(\d+)\s*winners?",
        r"winners?\s*[:\-]\s*(\d+)",
        r"winner\s*count\s*[:\-]\s*(\d+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                return int(
                    match.group(1)
                )

            except ValueError:
                continue

    return None


def get_invite_url(
    message: discord.Message
):

    text = collect_text(
        message
    )

    match = re.search(
        r"https?://"
        r"(?:discord\.gg|discord\.com/invite)"
        r"/[A-Za-z0-9\-]+",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(0)

    for row in message.components:

        for component in row.children:

            url = getattr(
                component,
                "url",
                None
            )

            if not url:
                continue

            if (
                "discord.gg/"
                in url
                or
                "discord.com/invite/"
                in url
            ):
                return url

    return None


def get_prize(
    message: discord.Message
):

    if not message.embeds:
        return "Unknown"

    embed = message.embeds[0]

    if embed.title:

        title = embed.title.strip()

        if (
            title
            and "giveaway"
            not in title.lower()
        ):
            return title[:200]

    if embed.description:

        lines = [
            line.strip()
            for line
            in embed.description.splitlines()
            if line.strip()
        ]

        for line in lines:

            if "prize" in line.lower():

                value = re.sub(
                    r"^.*?prize\s*[:\-]?\s*",
                    "",
                    line,
                    flags=re.IGNORECASE
                ).strip()

                if value:
                    return value[:200]

        if lines:
            return lines[0][:200]

    return "Unknown"


def is_giveaway(
    message: discord.Message
) -> bool:

    if not message.author.bot:
        return False

    if (
        TARGET_GIVEAWAY_BOT_ID
        and str(message.author.id)
        != TARGET_GIVEAWAY_BOT_ID
    ):
        return False

    text = collect_text(
        message
    )

    lower = text.lower()

    score = 0

    if message.embeds:
        score += 2

    if has_duration(text):
        score += 2

    if get_winner_count(text):
        score += 2

    if any(
        x in lower
        for x in (
            "participant",
            "participants",
            "entry",
            "entries"
        )
    ):
        score += 2

    if any(
        x in lower
        for x in (
            "giveaway",
            "enter to win",
            "click to enter",
            "join giveaway",
            "participate"
        )
    ):
        score += 2

    for row in message.components:

        for component in row.children:

            label = str(
                getattr(
                    component,
                    "label",
                    ""
                ) or ""
            ).lower()

            custom_id = str(
                getattr(
                    component,
                    "custom_id",
                    ""
                ) or ""
            ).lower()

            if any(
                x in label
                for x in (
                    "enter",
                    "join",
                    "giveaway",
                    "participate"
                )
            ):
                score += 3

            if any(
                x in custom_id
                for x in (
                    "giveaway",
                    "enter",
                    "participate"
                )
            ):
                score += 2

    return score >= 5


async def process_message(
    message: discord.Message
):

    if not message.author.bot:
        return

    if not is_giveaway(message):
        return

    if database.giveaway_exists(
        message.id
    ):
        return

    prize = get_prize(
        message
    )

    winner_count = get_winner_count(
        collect_text(message)
    )

    invite_url = get_invite_url(
        message
    )

    guild_id = (
        message.guild.id
        if message.guild
        else None
    )

    database.save_detected_giveaway(
        message_id=message.id,
        guild_id=guild_id,
        channel_id=message.channel.id,
        jump_url=message.jump_url,
        prize=prize,
        winner_count=winner_count,
        invite_url=invite_url
    )

    print(
        "=" * 60
    )

    print(
        "🎉 GIVEAWAY DETECTED"
    )

    print(
        f"Bot: {message.author}"
    )

    print(
        f"Server: "
        f"{message.guild.name if message.guild else 'Unknown'}"
    )

    print(
        f"Prize: {prize}"
    )

    print(
        f"Winners: "
        f"{winner_count or 'Unknown'}"
    )

    print(
        f"Invite: "
        f"{invite_url or 'NOT FOUND'}"
    )

    print(
        f"Message: "
        f"{message.jump_url}"
    )

    print(
        "=" * 60
    )

    await auto_join.notify_users(
        bot=message.client,
        message=message,
        prize=prize,
        winner_count=winner_count,
        invite_url=invite_url
    )