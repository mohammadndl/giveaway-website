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


def setup(
    bot
):

    print(
        "[DETECTOR] Ready."
    )

    print(
        "[DETECTOR] Target bot: "
        f"{TARGET_GIVEAWAY_BOT_ID or 'ALL BOTS'}"
    )


def get_message_text(
    message
):

    parts = [
        message.content or ""
    ]

    for embed in message.embeds:

        parts.append(
            embed.title or ""
        )

        parts.append(
            embed.description or ""
        )

        if embed.author:

            parts.append(
                embed.author.name or ""
            )

        if embed.footer:

            parts.append(
                embed.footer.text or ""
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

            if label:

                parts.append(
                    str(label)
                )

            if custom_id:

                parts.append(
                    str(custom_id)
                )

    return " ".join(
        parts
    )


def looks_like_giveaway(
    message
):

    if not message.author.bot:

        return False

    if (
        TARGET_GIVEAWAY_BOT_ID
        and str(message.author.id)
        != TARGET_GIVEAWAY_BOT_ID
    ):

        return False

    text = get_message_text(
        message
    )

    lower = text.lower()

    score = 0

    # Embed is a strong giveaway signal.
    if message.embeds:

        score += 2

    # Timing/countdown.
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

    # Participant/entry information.
    if any(
        word in lower
        for word in (
            "participants",
            "participant",
            "entries",
            "entries:",
            "enter"
        )
    ):

        score += 2

    # Giveaway structural words.
    if any(
        word in lower
        for word in (
            "giveaway",
            "enter giveaway",
            "enter to win",
            "click to enter",
            "join giveaway"
        )
    ):

        score += 2

    # Giveaway-style buttons.
    for row in message.components:

        for component in row.children:

            label = getattr(
                component,
                "label",
                None
            )

            if not label:
                continue

            label = label.lower()

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


def extract_prize(
    message
):

    if not message.embeds:

        return "Unknown prize"

    embed = message.embeds[0]

    if embed.title:

        title = embed.title.strip()

        if (
            "giveaway"
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

    return "Unknown prize"


def extract_winner_count(
    message
):

    text = get_message_text(
        message
    )

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

        if match:

            try:

                return int(
                    match.group(1)
                )

            except ValueError:

                pass

    return None


def extract_invite(
    message
):

    text = get_message_text(
        message
    )

    # Search message/embed text.
    match = re.search(
        r"https?://"
        r"(?:discord\.gg|discord\.com/invite)"
        r"/[A-Za-z0-9\-]+",
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(0)

    # Search link buttons.
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


async def get_user_for_dm(
    bot,
    user_id
):

    try:

        # IMPORTANT:
        #
        # Do NOT search guild.members.
        #
        # fetch_user() retrieves the Discord user
        # directly from their ID.
        #
        # This allows users who enabled Auto Join
        # to be notified even if they are not in one
        # of the bot's servers.

        return await bot.fetch_user(
            int(user_id)
        )

    except discord.NotFound:

        print(
            f"[AUTO JOIN] "
            f"User {user_id} not found."
        )

    except discord.HTTPException as error:

        print(
            f"[AUTO JOIN] "
            f"Could not fetch {user_id}: "
            f"{error}"
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
        "[AUTO JOIN] "
        f"{len(user_ids)} enabled user(s)."
    )

    for user_id in user_ids:

        user = await get_user_for_dm(
            bot,
            user_id
        )

        if user is None:

            continue

        embed = discord.Embed(
            title="🎉 GIVEAWAY DETECTED!",
            description=(
                f"🎁 **Prize:** "
                f"{prize}\n\n"

                f"🏆 **Winners:** "
                f"`{winner_count or 'Unknown'}`\n\n"

                f"📍 **Server:** "
                f"{message.guild.name "
                if message.guild
                else "Unknown"
                }"
                "\n\n"
                "Join the server and enter "
                "the giveaway!"
            )
        )

        embed.set_footer(
            text="Giveaway Tracker • Auto Join"
        )

        view = discord.ui.View(
            timeout=None
        )

        # Server invite.
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
                "[AUTO JOIN] "
                f"No server invite found for "
                f"giveaway {message.id}"
            )

        # Direct giveaway message.
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
                "[AUTO JOIN] "
                f"DM sent to {user_id}"
            )

        except discord.Forbidden:

            print(
                "[AUTO JOIN] "
                f"Cannot DM {user_id}. "
                "The user may have DMs disabled "
                "or blocked the bot."
            )

        except discord.HTTPException as error:

            print(
                "[AUTO JOIN] "
                f"DM error for {user_id}: "
                f"{error}"
            )


async def detect_winner(
    message
):

    text = get_message_text(
        message
    )

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
                f"🔗 **Winning message:**\n"
                f"{message.jump_url}"
            )

            print(
                "[WINNER] "
                f"DM sent to {user.id}"
            )

        except discord.Forbidden:

            print(
                "[WINNER] "
                f"Cannot DM {user.id}"
            )

        except discord.HTTPException as error:

            print(
                "[WINNER ERROR] "
                f"{user.id}: {error}"
            )


async def process_message(
    message
):

    if not message.author.bot:

        return

    # Check winner announcements.
    await detect_winner(
        message
    )

    # Check whether this is a giveaway.
    if not looks_like_giveaway(
        message
    ):

        return

    # Never process the same giveaway twice.
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

    print(
        "🎉 GIVEAWAY DETECTED"
    )

    print(
        f"Server: "
        f"{message.guild.name "
        if message.guild
        else "Unknown"
        }"
    )

    print(
        f"Prize: {prize}"
    )

    print(
        f"Winners: {winner_count}"
    )

    print(
        f"Message: {message.jump_url}"
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