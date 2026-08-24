import os
import re

import discord

import database


TARGET_GIVEAWAY_BOT_ID = (
    os.getenv("TARGET_GIVEAWAY_BOT_ID", "").strip()
    or None
)


def setup(bot):
    print("[DETECTOR] Ready.")
    print(
        "[DETECTOR] Target bot: "
        + (
            TARGET_GIVEAWAY_BOT_ID
            if TARGET_GIVEAWAY_BOT_ID
            else "ALL BOTS"
        )
    )


def get_message_text(message):
    parts = []

    if message.content:
        parts.append(message.content)

    for embed in message.embeds:

        if embed.title:
            parts.append(embed.title)

        if embed.description:
            parts.append(embed.description)

        if embed.author:
            if embed.author.name:
                parts.append(embed.author.name)

        if embed.footer:
            if embed.footer.text:
                parts.append(embed.footer.text)

        for field in embed.fields:

            if field.name:
                parts.append(field.name)

            if field.value:
                parts.append(field.value)

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

            if label:
                parts.append(str(label))

            if custom_id:
                parts.append(str(custom_id))

    return " ".join(parts)


def looks_like_giveaway(message):

    if not message.author.bot:
        return False

    if (
        TARGET_GIVEAWAY_BOT_ID
        and str(message.author.id)
        != TARGET_GIVEAWAY_BOT_ID
    ):
        return False

    text = get_message_text(message)
    lower = text.lower()

    score = 0

    # Embeds are a strong giveaway signal.
    if message.embeds:
        score += 2

    # Duration / countdown.
    if re.search(
        r"\b\d+\s*"
        r"(s|sec|secs|second|seconds|"
        r"m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|"
        r"d|day|days)\b",
        text,
        re.IGNORECASE
    ):
        score += 2

    # Winner count.
    if re.search(
        r"\b\d+\s*winners?\b",
        text,
        re.IGNORECASE
    ):
        score += 2

    # Participant information.
    if any(
        word in lower
        for word in (
            "participants",
            "participant",
            "entries",
            "entry",
            "enter"
        )
    ):
        score += 2

    # Giveaway-related structure.
    if any(
        phrase in lower
        for phrase in (
            "giveaway",
            "enter giveaway",
            "enter to win",
            "click to enter",
            "join giveaway"
        )
    ):
        score += 2

    # Giveaway buttons.
    for row in message.components:

        for component in row.children:

            label = getattr(
                component,
                "label",
                None
            )

            if not label:
                continue

            label = str(label).lower()

            if any(
                word in label
                for word in (
                    "enter",
                    "join",
                    "giveaway",
                    "participate"
                )
            ):
                score += 3

    return score >= 5


def extract_prize(message):

    if not message.embeds:
        return "Unknown prize"

    embed = message.embeds[0]

    if embed.title:

        title = embed.title.strip()

        if "giveaway" not in title.lower():
            return title[:200]

    if embed.description:

        lines = [
            line.strip()
            for line in embed.description.splitlines()
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

    return "Unknown prize"


def extract_winner_count(message):

    text = get_message_text(message)

    patterns = (
        r"(\d+)\s*winners?",
        r"winners?\s*[:\-]\s*(\d+)"
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:
            continue

        try:
            return int(match.group(1))
        except ValueError:
            pass

    return None


def extract_invite(message):

    text = get_message_text(message)

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
                "discord.gg/" in url
                or
                "discord.com/invite/" in url
            ):
                return url

    return None


async def get_user_for_dm(bot, user_id):

    try:

        # Fetch the user directly from Discord.
        #
        # We do NOT use guild.members here.
        # Therefore the user does not need to already
        # be inside the bot's server.

        user = await bot.fetch_user(
            int(user_id)
        )

        return user

    except discord.NotFound:

        print(
            f"[AUTO JOIN] User {user_id} "
            "was not found."
        )

    except discord.HTTPException as error:

        print(
            f"[AUTO JOIN] Failed to fetch "
            f"user {user_id}: {error}"
        )

    return None


async def notify_auto_join_users(
    message,
    prize,
    winner_count,
    invite_url
):

    bot = message.client

    user_ids = (
        database.get_auto_join_users()
    )

    print(
        f"[AUTO JOIN] "
        f"{len(user_ids)} enabled user(s)."
    )

    for user_id in user_ids:

        user = await get_user_for_dm(
            bot,
            user_id
        )

        if user is None:
            continue

        server_name = "Unknown Server"

        if message.guild:
            server_name = message.guild.name

        description = (
            f"🎁 **Prize:** {prize}\n\n"
            f"🏆 **Winners:** "
            f"`{winner_count or 'Unknown'}`\n\n"
            f"📍 **Server:** {server_name}\n\n"
            "Join the server and enter "
            "the giveaway!"
        )

        embed = discord.Embed(
            title="🎉 GIVEAWAY DETECTED!",
            description=description
        )

        embed.set_footer(
            text="Giveaway Tracker • Auto Join"
        )

        view = discord.ui.View(
            timeout=None
        )

        if invite_url:

            view.add_item(
                discord.ui.Button(
                    label="Join Server",
                    emoji="🔗",
                    style=discord.ButtonStyle.link,
                    url=invite_url
                )
            )

        else:

            print(
                f"[AUTO JOIN] No server invite "
                f"found for giveaway "
                f"{message.id}"
            )

        view.add_item(
            discord.ui.Button(
                label="Open Giveaway",
                emoji="🎉",
                style=discord.ButtonStyle.link,
                url=message.jump_url
            )
        )

        try:

            await user.send(
                embed=embed,
                view=view
            )

            print(
                f"[AUTO JOIN] DM sent to "
                f"{user_id}"
            )

        except discord.Forbidden:

            print(
                f"[AUTO JOIN] Cannot DM "
                f"{user_id}. "
                "Their Discord privacy settings "
                "may prevent the DM."
            )

        except discord.HTTPException as error:

            print(
                f"[AUTO JOIN] DM error for "
                f"{user_id}: {error}"
            )


async def detect_winner(message):

    text = get_message_text(message)
    lower = text.lower()

    if not any(
        word in lower
        for word in (
            "winner",
            "won",
            "congratulations",
            "congrats"
        )
    ):
        return

    if not message.mentions:
        return

    for user in message.mentions:

        if user.bot:
            continue

        if not database.auto_join_enabled(
            user.id
        ):
            continue

        try:

            await user.send(
                "🏆 **YOU WON!**\n\n"
                "🎉 Congratulations!\n\n"
                "🔗 **Winning message:**\n"
                f"{message.jump_url}"
            )

            print(
                f"[WINNER] DM sent to "
                f"{user.id}"
            )

        except discord.Forbidden:

            print(
                f"[WINNER] Cannot DM "
                f"{user.id}"
            )

        except discord.HTTPException as error:

            print(
                f"[WINNER ERROR] "
                f"{user.id}: {error}"
            )


async def process_message(message):

    if not message.author.bot:
        return

    # Check winner announcements.
    await detect_winner(message)

    # Check giveaway structure.
    if not looks_like_giveaway(message):
        return

    # Prevent duplicate detection.
    if database.giveaway_exists(
        message.id
    ):
        return

    prize = extract_prize(
        message
    )

    winner_count = extract_winner_count(
        message
    )

    invite_url = extract_invite(
        message
    )

    guild_name = "Unknown"

    if message.guild:
        guild_name = message.guild.name

    database.save_giveaway(
        message_id=message.id,
        guild_id=(
            message.guild.id
            if message.guild
            else None
        ),
        channel_id=message.channel.id,
        jump_url=message.jump_url,
        prize=prize,
        winners=winner_count
    )

    print("=" * 60)
    print("🎉 GIVEAWAY DETECTED")
    print(f"Server: {guild_name}")
    print(f"Prize: {prize}")
    print(
        f"Winners: "
        f"{winner_count or 'Unknown'}"
    )
    print(
        f"Message: "
        f"{message.jump_url}"
    )
    print(
        f"Invite: "
        f"{invite_url or 'NOT FOUND'}"
    )
    print("=" * 60)

    await notify_auto_join_users(
        message=message,
        prize=prize,
        winner_count=winner_count,
        invite_url=invite_url
    )