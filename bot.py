import os
import re
import sqlite3
import asyncio
import unicodedata
from datetime import datetime

import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ITAD_API_KEY = os.getenv("ITAD_API_KEY")

GAME_FORUM_CHANNEL_ID = os.getenv("GAME_FORUM_CHANNEL_ID")

PRICE_CHECK_MINUTES = int(os.getenv("PRICE_CHECK_MINUTES", "30"))
SALE_THRESHOLD_PERCENT = float(
    os.getenv("SALE_THRESHOLD_PERCENT", "1")
)

DATABASE_FILE = "game_bot.db"

ITAD_BASE_URL = "https://api.isthereanydeal.com"


# Major storefronts we want to display.
# ITAD may have additional smaller/marketplace stores,
# so these are intentionally filtered out.
MAJOR_STORES = {
    "Steam",
    "Epic Games Store",
    "GOG",
    "Humble Store",
    "Ubisoft Store",
    "EA Store",
    "Microsoft Store",
    "Fanatical",
}


# ============================================================
# DISCORD CLIENT
# ============================================================

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


# ============================================================
# STATE
# ============================================================

# Pending game selections.
#
# Example:
# pending_selections[thread_id] = {
#     "results": [...],
#     "original_author_id": 123456789
# }
pending_selections = {}

# Prevent processing the same forum thread more than once
# during the current bot session.
processed_threads = set()


# ============================================================
# DATABASE
# ============================================================

def init_database():
    conn = sqlite3.connect(DATABASE_FILE)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watches (
            thread_id INTEGER PRIMARY KEY,
            game_id TEXT NOT NULL,
            game_title TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            last_sale_state INTEGER DEFAULT 0,
            last_price REAL,
            last_shop TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def add_watch(
    thread_id,
    game_id,
    game_title,
    author_id,
    last_sale_state=0,
    last_price=None,
    last_shop=None,
):
    conn = sqlite3.connect(DATABASE_FILE)

    conn.execute(
        """
        INSERT OR REPLACE INTO watches (
            thread_id,
            game_id,
            game_title,
            author_id,
            last_sale_state,
            last_price,
            last_shop,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            thread_id,
            game_id,
            game_title,
            author_id,
            last_sale_state,
            last_price,
            last_shop,
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def get_watches():
    conn = sqlite3.connect(DATABASE_FILE)

    rows = conn.execute(
        """
        SELECT
            thread_id,
            game_id,
            game_title,
            author_id,
            last_sale_state,
            last_price,
            last_shop,
            created_at
        FROM watches
        """
    ).fetchall()

    conn.close()

    return rows


def update_watch_state(
    thread_id,
    sale_state,
    price=None,
    shop=None,
):
    conn = sqlite3.connect(DATABASE_FILE)

    conn.execute(
        """
        UPDATE watches
        SET
            last_sale_state = ?,
            last_price = ?,
            last_shop = ?
        WHERE thread_id = ?
        """,
        (
            sale_state,
            price,
            shop,
            thread_id,
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# TITLE MATCHING
# ============================================================

def normalize_title(title):
    """
    Normalize a title so that things like:

        R.E.P.O.
        repo
        R E P O

    can be compared more intelligently.
    """

    if not title:
        return ""

    title = unicodedata.normalize(
        "NFKD",
        title,
    )

    title = "".join(
        character
        for character in title
        if not unicodedata.combining(character)
    )

    title = title.lower()

    # Remove common trademark/copyright symbols.
    title = title.replace("™", "")
    title = title.replace("®", "")
    title = title.replace("©", "")

    # Remove everything except letters and numbers.
    title = re.sub(
        r"[^a-z0-9]+",
        "",
        title,
    )

    return title


def titles_match(title1, title2):
    return normalize_title(title1) == normalize_title(title2)


# ============================================================
# ITAD API
# ============================================================

async def itad_request(
    session,
    method,
    endpoint,
    **kwargs,
):
    url = f"{ITAD_BASE_URL}{endpoint}"

    headers = kwargs.pop("headers", {})

    headers["ITAD-API-Key"] = ITAD_API_KEY

    try:
        async with session.request(
            method,
            url,
            headers=headers,
            **kwargs,
        ) as response:

            if response.status == 429:
                retry_after = response.headers.get(
                    "Retry-After",
                    "unknown",
                )

                print(
                    f"ITAD rate limit reached. "
                    f"Retry-After: {retry_after}"
                )

                return None

            if response.status >= 400:
                text = await response.text()

                print(
                    f"ITAD API error {response.status}: "
                    f"{text}"
                )

                return None

            return await response.json()

    except Exception as error:
        print(
            f"ITAD request failed: {error}"
        )

        return None


async def search_itad(title):
    async with aiohttp.ClientSession() as session:

        results = await itad_request(
            session,
            "GET",
            "/games/search/v1",
            params={
                "title": title,
                "results": 5,
            },
        )

        if not results:
            return []

        return results


async def get_price_overview(game_id):
    async with aiohttp.ClientSession() as session:

        result = await itad_request(
            session,
            "POST",
            "/games/overview/v2",
            params={
                "country": "US",
            },
            json=[
                game_id,
            ],
        )

        return result


async def get_game_prices(game_id):
    async with aiohttp.ClientSession() as session:

        result = await itad_request(
            session,
            "POST",
            "/games/prices/v3",
            params={
                "country": "US",
            },
            json=[
                game_id,
            ],
        )

        return result


# ============================================================
# DEAL RATING
# ============================================================

def get_deal_rating(
    current_price,
    historical_low,
    discount_percent,
):
    """
    Determine how good the current deal is compared
    with the game's historical low.
    """

    if current_price is None:
        return (
            "⚪ No Current Price",
            "No current price available.",
        )

    if historical_low is None or historical_low <= 0:

        if discount_percent >= 50:
            return (
                "🟢 Great Deal",
                f"{discount_percent:.0f}% off",
            )

        elif discount_percent >= 20:
            return (
                "🟡 Good Deal",
                f"{discount_percent:.0f}% off",
            )

        elif discount_percent >= SALE_THRESHOLD_PERCENT:
            return (
                "🏷️ On Sale",
                f"{discount_percent:.0f}% off",
            )

        else:
            return (
                "⚪ Regular Price",
                "No significant discount.",
            )

    percent_above_low = (
        (current_price - historical_low)
        / historical_low
    ) * 100

    if percent_above_low <= 5:

        return (
            "🔥 Exceptional Deal",
            "At or extremely close to the historical low.",
        )

    elif percent_above_low <= 15:

        return (
            "🟢 Great Deal",
            f"Only {percent_above_low:.0f}% above the historical low.",
        )

    elif percent_above_low <= 30:

        return (
            "🟡 Good Deal",
            f"{percent_above_low:.0f}% above the historical low.",
        )

    elif discount_percent >= SALE_THRESHOLD_PERCENT:

        return (
            "🏷️ On Sale",
            f"{discount_percent:.0f}% off.",
        )

    else:

        return (
            "⚪ Regular Price",
            "Not currently on sale.",
        )


# ============================================================
# PRICE FORMATTING
# ============================================================

def format_price(price):
    if price is None:
        return "N/A"

    try:
        return f"${float(price):.2f}"

    except (ValueError, TypeError):
        return "N/A"


def build_store_price_line(deal):
    shop = deal.get("shop", {})
    price = deal.get("price", {})

    shop_name = shop.get(
        "name",
        "Unknown Store",
    )

    amount = price.get(
        "amount"
    )

    currency = price.get(
        "currency",
        "USD",
    )

    cut = deal.get(
        "cut",
        0,
    )

    url = deal.get(
        "url"
    )

    formatted_price = format_price(amount)

    if currency != "USD":
        formatted_price = (
            f"{formatted_price} {currency}"
        )

    if cut and cut > 0:

        price_text = (
            f"**{shop_name}** — "
            f"{formatted_price} "
            f"({cut:.0f}% off)"
        )

    else:

        price_text = (
            f"**{shop_name}** — "
            f"{formatted_price}"
        )

    if url:
        price_text += (
            f" • [Buy / View Deal]({url})"
        )

    return price_text


# ============================================================
# SEND GAME PRICE INFORMATION
# ============================================================

async def send_game_price(
    channel,
    selected_game,
):
    game_id = selected_game.get(
        "id"
    )

    game_title = selected_game.get(
        "title",
        "Unknown Game",
    )

    print(
        f"Selected game: {game_title}"
    )

    print(
        f"Game ID: {game_id}"
    )

    print(
        "Looking up prices..."
    )

    overview = await get_price_overview(
        game_id
    )

    if not overview:

        await channel.send(
            "I couldn't retrieve pricing information "
            "for that game right now."
        )

        return False

    # --------------------------------------------------------
    # ITAD overview response
    # --------------------------------------------------------

    overview_game = None

    if isinstance(overview, dict):

        prices = overview.get(
            "prices",
            []
        )

        if prices:
            overview_game = prices[0]

    elif isinstance(overview, list):

        if overview:
            overview_game = overview[0]

    if not overview_game:

        await channel.send(
            "I found the game, but IsThereAnyDeal "
            "didn't return pricing information."
        )

        return False

    current = overview_game.get(
        "current",
        {}
    )

    lowest = overview_game.get(
        "lowest",
        {}
    )

    current_price = current.get(
        "price",
        {}
    ).get(
        "amount"
    )

    historical_low = lowest.get(
        "price",
        {}
    ).get(
        "amount"
    )

    discount_percent = current.get(
        "cut",
        0
    )

    current_shop = current.get(
        "shop",
        {}
    )

    current_shop_name = current_shop.get(
        "name",
        "Unknown Store"
    )

    current_url = current.get(
        "url"
    )

    # --------------------------------------------------------
    # Deal rating
    # --------------------------------------------------------

    rating, rating_reason = get_deal_rating(
        current_price,
        historical_low,
        discount_percent,
    )

    # --------------------------------------------------------
    # Detailed prices
    # --------------------------------------------------------

    prices_response = await get_game_prices(
        game_id
    )

    detailed_game = None

    # /games/prices/v3 returns a LIST directly.
    if prices_response:

        if isinstance(
            prices_response,
            list
        ):

            detailed_game = (
                prices_response[0]
            )

        elif isinstance(
            prices_response,
            dict
        ):

            detailed_game = (
                prices_response
            )

    deals = []

    if detailed_game:

        deals = detailed_game.get(
            "deals",
            []
        )

    # --------------------------------------------------------
    # Store filtering
    # --------------------------------------------------------

    deals = [
        deal
        for deal in deals
        if deal.get(
            "shop",
            {}
        ).get(
            "name"
        ) in MAJOR_STORES
    ]

    # Cheapest stores first.
    deals.sort(
        key=lambda deal: deal.get(
            "price",
            {}
        ).get(
            "amount",
            float("inf")
        )
    )

    # --------------------------------------------------------
    # Build embed
    # --------------------------------------------------------

    embed = discord.Embed(
        title=game_title,
        description=(
            f"**Deal Rating:** {rating}\n"
            f"{rating_reason}"
        ),
    )

    # --------------------------------------------------------
    # Current best price
    # --------------------------------------------------------

    if current_price is not None:

        current_price_text = (
            f"{format_price(current_price)} "
            f"at **{current_shop_name}**"
        )

        if discount_percent > 0:

            current_price_text += (
                f"\n{discount_percent:.0f}% off"
            )

        if current_url:

            current_price_text += (
                f"\n[View Deal]({current_url})"
            )

        embed.add_field(
            name="Best Current Price",
            value=current_price_text,
            inline=True,
        )

    # --------------------------------------------------------
    # Historical low
    # --------------------------------------------------------

    if historical_low is not None:

        historical_text = (
            f"{format_price(historical_low)}"
        )

        if current_price is not None:

            if historical_low > 0:

                difference = (
                    (
                        current_price
                        - historical_low
                    )
                    / historical_low
                ) * 100

                if difference <= 0:

                    historical_text += (
                        "\n🔥 At historical low!"
                    )

                else:

                    historical_text += (
                        f"\n{difference:.0f}% "
                        f"above historical low"
                    )

        embed.add_field(
            name="Historical Low",
            value=historical_text,
            inline=True,
        )

    # --------------------------------------------------------
    # Store prices
    # --------------------------------------------------------

    if deals:

        store_lines = []
        total_length = 0

        # Discord embed field values have a 1024
        # character limit. Keep a little safety room.
        MAX_FIELD_LENGTH = 1000

        for deal in deals:

            line = build_store_price_line(
                deal
            )

            additional_length = len(line)

            if store_lines:
                additional_length += 1

            if (
                total_length
                + additional_length
                > MAX_FIELD_LENGTH
            ):
                break

            store_lines.append(line)

            total_length += (
                additional_length
            )

        if store_lines:

            embed.add_field(
                name="Major Store Prices",
                value="\n".join(
                    store_lines
                ),
                inline=False,
            )

    # --------------------------------------------------------
    # Thumbnail / artwork
    # --------------------------------------------------------

    assets = selected_game.get(
        "assets",
        {}
    )

    boxart = assets.get(
        "boxart"
    )

    if boxart:

        embed.set_thumbnail(
            url=boxart
        )

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    embed.set_footer(
        text=(
            "Pricing provided by "
            "IsThereAnyDeal"
        )
    )

    await channel.send(
        embed=embed
    )

    print(
        "Deal information sent to Discord."
    )

    return True


# ============================================================
# PROCESS SELECTED GAME
# ============================================================

async def process_game_selection(
    message,
    selected_game,
):
    game_title = selected_game.get(
        "title",
        "Unknown Game",
    )

    game_id = selected_game.get(
        "id"
    )

    print(
        "=================================================="
    )

    print(
        f"User selected: {game_title}"
    )

    print(
        f"Selected game: {game_title}"
    )

    print(
        f"Game ID: {game_id}"
    )

    success = await send_game_price(
        message.channel,
        selected_game,
    )

    if success:

        add_watch(
            thread_id=message.channel.id,
            game_id=game_id,
            game_title=game_title,
            author_id=message.author.id,
        )

        print(
            f"Watching {game_title} "
            f"for future price changes."
        )


# ============================================================
# FORUM VALIDATION
# ============================================================

def is_allowed_forum(thread):
    if not GAME_FORUM_CHANNEL_ID:
        return True

    try:
        forum_id = int(
            GAME_FORUM_CHANNEL_ID
        )

    except ValueError:
        print(
            "Invalid GAME_FORUM_CHANNEL_ID "
            "in .env"
        )

        return False

    return (
        thread.parent_id
        == forum_id
    )


# ============================================================
# SALE MONITORING
# ============================================================

async def check_watched_games():
    watches = get_watches()

    if not watches:
        return

    print(
        "=================================================="
    )

    print(
        f"Checking {len(watches)} watched game(s)..."
    )

    print(
        "=================================================="
    )

    for watch in watches:

        (
            thread_id,
            game_id,
            game_title,
            author_id,
            last_sale_state,
            last_price,
            last_shop,
            created_at,
        ) = watch

        try:

            overview = await get_price_overview(
                game_id
            )

            if not overview:
                continue

            overview_game = None

            if isinstance(
                overview,
                dict
            ):

                prices = overview.get(
                    "prices",
                    []
                )

                if prices:
                    overview_game = prices[0]

            elif isinstance(
                overview,
                list
            ):

                if overview:
                    overview_game = overview[0]

            if not overview_game:
                continue

            current = overview_game.get(
                "current",
                {}
            )

            price_data = current.get(
                "price",
                {}
            )

            current_price = price_data.get(
                "amount"
            )

            discount_percent = current.get(
                "cut",
                0
            )

            shop = current.get(
                "shop",
                {}
            )

            shop_name = shop.get(
                "name",
                "Unknown Store"
            )

            sale_state = (
                1
                if discount_percent
                >= SALE_THRESHOLD_PERCENT
                else 0
            )

            # ------------------------------------------------
            # Detect a transition into a sale.
            # ------------------------------------------------

            if (
                sale_state == 1
                and last_sale_state == 0
            ):

                try:

                    thread = client.get_channel(
                        thread_id
                    )

                    if thread:

                        rating, rating_reason = (
                            get_deal_rating(
                                current_price,
                                None,
                                discount_percent,
                            )
                        )

                        message_text = (
                            f"## 🏷️ New Deal!\n"
                            f"**{game_title}** is now "
                            f"**{discount_percent:.0f}% off** "
                            f"at **{shop_name}**.\n\n"
                            f"**Price:** "
                            f"{format_price(current_price)}\n"
                            f"**Rating:** {rating}\n"
                            f"{rating_reason}"
                        )

                        if current.get(
                            "url"
                        ):

                            message_text += (
                                f"\n\n"
                                f"[View Deal]"
                                f"({current['url']})"
                            )

                        await thread.send(
                            message_text
                        )

                        print(
                            f"SALE ALERT: "
                            f"{game_title}"
                        )

                except Exception as error:

                    print(
                        f"Could not send sale alert "
                        f"for {game_title}: {error}"
                    )

            # ------------------------------------------------
            # Update state.
            # ------------------------------------------------

            update_watch_state(
                thread_id,
                sale_state,
                current_price,
                shop_name,
            )

            # Be polite to the API.
            await asyncio.sleep(1)

        except Exception as error:

            print(
                f"Error checking "
                f"{game_title}: {error}"
            )


# ============================================================
# PRICE CHECK LOOP
# ============================================================

@tasks.loop(
    minutes=PRICE_CHECK_MINUTES
)
async def price_check_loop():

    await check_watched_games()


@price_check_loop.before_loop
async def before_price_check_loop():

    await client.wait_until_ready()


# ============================================================
# DISCORD EVENTS
# ============================================================

@client.event
async def on_ready():

    print(
        f"Logged in as {client.user}"
    )

    print(
        "Game Recommendation Bot is ready!"
    )

    if GAME_FORUM_CHANNEL_ID:

        print(
            f"Monitoring forum channel: "
            f"{GAME_FORUM_CHANNEL_ID}"
        )

    else:

        print(
            "Monitoring all accessible forums."
        )

    print(
        f"Sale threshold: "
        f"{SALE_THRESHOLD_PERCENT:g}%"
    )

    print(
        f"Price check interval: "
        f"{PRICE_CHECK_MINUTES} minutes"
    )

    print(
        "=================================================="
    )

    if not price_check_loop.is_running():

        price_check_loop.start()


@client.event
async def on_message(message):

    # Ignore ourselves and other bots.
    if message.author.bot:
        return

    # --------------------------------------------------------
    # Handle pending game selection first.
    # --------------------------------------------------------

    thread_id = message.channel.id

    if thread_id in pending_selections:

        selection = pending_selections[
            thread_id
        ]

        # Only the person who created the
        # original suggestion can select.
        if (
            message.author.id
            != selection[
                "original_author_id"
            ]
        ):
            return

        content = message.content.strip()

        if not content.isdigit():

            await message.channel.send(
                "Please reply with the number "
                "of the game you want."
            )

            return

        selection_number = int(
            content
        )

        results = selection[
            "results"
        ]

        if (
            selection_number < 1
            or selection_number > len(results)
        ):

            await message.channel.send(
                f"Please choose a number "
                f"between 1 and {len(results)}."
            )

            return

        selected_game = results[
            selection_number - 1
        ]

        del pending_selections[
            thread_id
        ]

        await process_game_selection(
            message,
            selected_game,
        )

        return

    # --------------------------------------------------------
    # Only process Discord threads.
    # --------------------------------------------------------

    if not isinstance(
        message.channel,
        discord.Thread
    ):
        return

    thread = message.channel

    # --------------------------------------------------------
    # Only monitor configured forum.
    # --------------------------------------------------------

    if not is_allowed_forum(
        thread
    ):
        return

    # --------------------------------------------------------
    # Only process the original forum post.
    #
    # Forum starter messages have the same ID as
    # the thread.
    # --------------------------------------------------------

    if message.id != thread.id:
        return

    # --------------------------------------------------------
    # Prevent duplicate processing.
    # --------------------------------------------------------

    if thread.id in processed_threads:
        return

    processed_threads.add(
        thread.id
    )

    title = thread.name.strip()

    description = (
        message.content.strip()
    )

    print(
        "=================================================="
    )

    print(
        f"Forum Post: {title}"
    )

    print(
        f"Suggested By: "
        f"{message.author}"
    )

    print(
        f"Description: "
        f"{description}"
    )

    print(
        "Searching IsThereAnyDeal..."
    )

    # --------------------------------------------------------
    # Search ITAD.
    # --------------------------------------------------------

    results = await search_itad(
        title
    )

    print(
        f"Found {len(results)} result(s)."
    )

    if not results:

        await thread.send(
            f"I couldn't find a game matching "
            f"**{title}** on IsThereAnyDeal."
        )

        return

    # --------------------------------------------------------
    # Look for exact normalized title match.
    # --------------------------------------------------------

    exact_match = None

    for result in results:

        result_title = result.get(
            "title",
            ""
        )

        if titles_match(
            title,
            result_title
        ):

            exact_match = result
            break

    # --------------------------------------------------------
    # Automatically select exact match.
    # --------------------------------------------------------

    if exact_match:

        print(
            f"Exact match found: "
            f"{exact_match.get('title')}"
        )

        await process_game_selection(
            message,
            exact_match,
        )

        return

    # --------------------------------------------------------
    # Ambiguous result.
    # --------------------------------------------------------

    pending_selections[
        thread.id
    ] = {
        "results": results,
        "original_author_id": (
            message.author.id
        ),
    }

    selection_lines = []

    for index, result in enumerate(
        results,
        start=1,
    ):

        result_title = result.get(
            "title",
            "Unknown Game",
        )

        selection_lines.append(
            f"**{index}.** {result_title}"
        )

    await thread.send(
        "I found several possible games. "
        "Please reply with the number of the "
        "correct one:\n\n"
        + "\n".join(
            selection_lines
        )
    )

    print(
        "Ambiguous game title. "
        "Waiting for user selection."
    )


# ============================================================
# STARTUP
# ============================================================

init_database()

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from .env"
    )

if not ITAD_API_KEY:
    raise RuntimeError(
        "ITAD_API_KEY is missing from .env"
    )

client.run(
    DISCORD_TOKEN
)