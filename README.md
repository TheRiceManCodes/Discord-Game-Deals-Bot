# 🎮 Discord Game Deals Bot

A Discord bot that monitors game suggestions in **Discord Forum Channels**, automatically identifies the suggested game, checks multiple game storefronts for current pricing, and notifies the discussion when a deal is available.

The bot uses **IsThereAnyDeal (ITAD)** as its primary game and pricing data source, allowing it to compare storefronts without requiring separate integrations with every individual game store.

---

## ✨ Features

### 🎯 Automatic Game Detection

The bot monitors accessible Discord Forum Channels and watches for new game suggestions.

For example:

> **R.E.P.O.**

The bot automatically searches IsThereAnyDeal for the game and attempts to identify the correct title.

---

### 🔎 Ambiguous Game Selection

If a suggestion could refer to multiple games, the bot does not blindly select the first result.

For example:

> **Batman**

could refer to:

* LEGO® Batman
* LEGO® Batman 2
* LEGO® Batman 3
* Batman: Arkham Knight
* Batman: Arkham City
* Batman: Arkham Asylum
* and many others

When multiple reasonable matches are found, the bot presents the available choices in Discord and allows the user to select the intended game.

---

### 💰 Multi-Store Price Checking

Once a game has been identified, the bot checks available storefront pricing through IsThereAnyDeal.

Depending on the game, this can include stores such as:

* Steam
* GOG
* Green Man Gaming
* Epic Games Store
* Humble Store
* Fanatical
* Other supported storefronts

The bot reports the current price, discount, store, and purchase link when available.

---

### 📉 Historical Low Tracking

The bot also compares the current price against the game's historical lowest known price.

Example:

```text
Current Price: $9.99
Current Discount: 0%

Historical Low: $6.49
Historical Low Discount: 35%
```

This allows users to determine whether a current sale is actually a good deal or whether they may want to wait for a better price.

---

### 🔔 Automatic Sale Monitoring

Games suggested in Discord can be added to the bot's watch list.

The bot periodically checks watched games for changes in pricing.

By default:

```text
Price Check Interval: 30 minutes
Sale Threshold: 1%
```

The bot is designed to avoid repeatedly notifying users about the same price.

A notification is generated when a watched game's sale state changes according to the configured threshold.

---

### 🧵 Forum Thread Integration

The bot associates watched games with the Discord Forum thread where they were suggested.

This means notifications can be sent directly back into the relevant discussion instead of being dumped into a separate channel.

The workflow is:

```text
User suggests game
        ↓
Forum post detected
        ↓
Game searched
        ↓
Game selected
        ↓
Prices retrieved
        ↓
Game added to watch list
        ↓
Periodic price checks
        ↓
Sale detected
        ↓
Discord notification
```

---

### 💾 SQLite Database

The bot uses SQLite for persistent storage.

The database stores watched games and their current state so that restarting the bot does not cause the watch list to disappear.

The database is automatically created when the bot runs.

Example database structure:

```sql
CREATE TABLE watches (
    thread_id INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL,
    game_title TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    last_sale_state INTEGER DEFAULT 0,
    last_price REAL,
    last_shop TEXT,
    created_at TEXT NOT NULL
);
```

The database file is:

```text
gamebot.db
```

---

## 🛠️ Technology

This project is written in Python.

### Core technologies

* Python
* `discord.py`
* IsThereAnyDeal API
* SQLite
* `python-dotenv`
* Async HTTP requests

Discord bots maintain a connection to Discord's Gateway so they can receive events such as new messages and forum activity.

---

# 🚀 Getting Started

## Requirements

You will need:

* Windows, macOS, or Linux
* Python 3.9+
* A Discord application/bot
* An IsThereAnyDeal API key
* A Discord server where you have permission to add the bot

The project was developed and tested using Python 3.14.

---

# 📥 Installation

Clone the repository:

```powershell
git clone https://github.com/TheRiceManCodes/Discord-Game-Deals-Bot.git
```

Enter the project directory:

```powershell
cd Discord-Game-Deals-Bot
```

---

## 🐍 Create a Virtual Environment

Windows:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see something similar to:

```text
(.venv) PS C:\...\Discord-Game-Deals-Bot>
```

---

## 📦 Install Dependencies

Run:

```powershell
python -m pip install -r requirements.txt
```

---

# 🔐 Configuration

The bot uses environment variables for sensitive credentials.

Create a file named:

```text
.env
```

in the root of the project.

Example:

```env
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
ITAD_API_KEY=YOUR_IS_THERE_ANY_DEAL_API_KEY
```

### ⚠️ Never commit `.env`

Your `.env` file contains secrets and should **never** be uploaded to GitHub.

The project should contain:

```text
.env
```

in `.gitignore`.

A safe repository should instead contain:

```text
.env.example
```

with placeholder values.

Example:

```env
DISCORD_TOKEN=
ITAD_API_KEY=
```

---

# 🤖 Creating the Discord Bot

Create an application through the Discord Developer Portal.

Create a bot user for the application and obtain the bot token.

### Important

The following values are different:

| Value          | Purpose                                   |
| -------------- | ----------------------------------------- |
| Bot Token      | Authenticates the bot                     |
| Application ID | Identifies the Discord application        |
| Public Key     | Used for interaction/request verification |
| Client Secret  | OAuth/application authentication          |

**The bot token is the value required by this project.**

Do not publish the bot token.

If the token is accidentally exposed, immediately regenerate it through the Discord Developer Portal.

---

# 🔑 Discord Intents

The bot needs access to message content in order to identify game suggestions.

Enable the appropriate privileged intent in the Discord Developer Portal.

The bot should also have permission to:

* View Channels
* Read Message History
* Send Messages
* Embed Links
* Use External Emojis, if applicable
* Create/Manage Threads where required
* Read Messages/View Channels

The exact permissions can be restricted further depending on how the bot is deployed.

---

# 🏪 IsThereAnyDeal

The bot uses IsThereAnyDeal to search for games and retrieve pricing information.

Create an IsThereAnyDeal API key and add it to:

```env
ITAD_API_KEY=YOUR_API_KEY
```

### Important

The **API key** is not the same thing as the IsThereAnyDeal client secret.

Use the API key provided for API access.

---

# ▶️ Running the Bot

With the virtual environment activated:

```powershell
python bot.py
```

A successful startup should look similar to:

```text
Logged in as GameRecomendations#4621
Game Recommendation Bot is ready!
Monitoring all accessible forums.
Sale threshold: 1%
Price check interval: 30 minutes
==================================================
Checking 0 watched game(s)...
==================================================
```

The bot will remain running and listen for Discord events.

---

# 🧪 Testing

Create a test post in a Discord Forum Channel accessible to the bot.

For example:

```text
R.E.P.O.
```

The bot should detect the post and search IsThereAnyDeal.

A successful lookup will look similar to:

```text
Forum Post: REPO
Suggested By: username
Description: Let's play this!

Searching IsThereAnyDeal...
Found 5 result(s).

Selected game: R.E.P.O.
Game ID: 0194dbe4-baf3-710a-a37e-54e36439ea6f

Looking up prices...
```

The bot then posts the pricing information back into the forum thread.

---

# ❓ Ambiguous Game Titles

Some suggestions are too vague to safely identify automatically.

For example:

```text
Batman
```

may return several games.

Instead of guessing, the bot asks the user to select the intended game.

After selection:

```text
User selected: LEGO® Batman 3: Beyond Gotham

Selected game: LEGO® Batman 3: Beyond Gotham
Game ID: 018d937e-f8c5-7010-a344-8bec5a532421

Looking up prices...
```

This prevents the bot from attaching the wrong game to a discussion.

---

# 💵 Price Notifications

The bot tracks the last known price state for watched games.

This prevents a game that remains on sale from generating a notification every time the scheduled price check runs.

For example:

```text
Initial check:
$19.99 → 20% off
```

The bot records that state.

Thirty minutes later:

```text
$19.99 → 20% off
```

No new notification is required.

If the price changes:

```text
$19.99 → $9.99
```

the bot can detect the change and notify the thread.

---

# 📊 Sale Threshold

The sale threshold determines how large of a price change is required before the bot considers it significant.

Default:

```text
1%
```

This can be adjusted in the bot configuration.

A threshold prevents insignificant price changes from generating unnecessary Discord notifications.

---

# 🗃️ Database

The bot creates:

```text
gamebot.db
```

This is a SQLite database.

It contains persistent watch information such as:

* Discord thread ID
* IsThereAnyDeal game ID
* Game title
* User who suggested the game
* Previous sale state
* Previous price
* Previous store
* Date/time the game was added

### Do not manually edit the database

Unless you know exactly what you are doing, allow the bot to manage the database.

The database can safely be backed up by copying:

```text
gamebot.db
```

---

# 🧹 Resetting the Watch List

If you need to completely reset the bot's watched games, stop the bot and remove:

```text
gamebot.db
```

Then start the bot again.

The database will be recreated automatically.

**Warning:** This removes the bot's stored watch information.

---

# 📁 Project Structure

A typical installation looks like:

```text
Discord-Game-Deals-Bot/
│
├── bot.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── .env
├── gamebot.db
│
└── .venv/
```

### Important files

| File               | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `bot.py`           | Main bot application                     |
| `requirements.txt` | Python dependencies                      |
| `.env`             | Private API keys and credentials         |
| `.env.example`     | Configuration template                   |
| `.gitignore`       | Prevents private/unwanted files from Git |
| `gamebot.db`       | Persistent SQLite database               |
| `README.md`        | Project documentation                    |

---

# 🔒 Git & Security

The following should **not** be committed to GitHub:

```text
.env
.venv/
__pycache__/
*.pyc
gamebot.db
```

Your `.gitignore` should include at minimum:

```gitignore
# Environment
.env
.env.*

# Allow the example configuration
!.env.example

# Python
__pycache__/
*.py[cod]
*$py.class

# Virtual environment
.venv/
venv/
env/

# SQLite database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

### If `.env` was already committed

Simply adding `.env` to `.gitignore` does **not** remove it from Git's history.

If a secret has been committed:

1. Immediately rotate/regenerate the exposed credential.
2. Remove the file from Git tracking.
3. Clean the repository history if necessary.

GitHub provides secret scanning and push protection specifically to help prevent credentials from being committed to repositories.

---

# 🐛 Troubleshooting

## `DISCORD_TOKEN not found in .env`

Make sure:

```text
.env
```

exists in the same directory as `bot.py`.

Check that the variable is spelled correctly:

```env
DISCORD_TOKEN=YOUR_TOKEN
```

Also make sure the file has actually been saved.

---

## `Invalid or expired API key`

If IsThereAnyDeal returns:

```text
HTTP 403
Invalid or expired api key
```

verify that you copied the **API key**, rather than the client secret.

---

## `ITAD returned HTTP 404`

A 404 generally means the requested API endpoint or resource could not be found.

Check that:

* The API endpoint is correct.
* The game ID is valid.
* The API request format matches the current ITAD API.

---

## Discord `400 Bad Request`

If Discord reports something such as:

```text
Invalid Form Body
```

check the contents of the embed being sent.

Discord imposes limits on embed fields and other message components.

The bot includes handling for long pricing information so that individual embed fields do not exceed Discord's limits.

---

## Bot Does Not Detect Forum Posts

Verify that:

* The bot can see the forum channel.
* The bot can read messages.
* Message Content Intent is enabled.
* The bot has access to the relevant forum.
* The bot process is actually running.

---

## Bot Cannot Send Messages

Verify that the bot has:

```text
View Channel
Send Messages
Embed Links
Read Message History
```

and any thread-specific permissions required by the server.

---

# 🔄 Future Improvements

The project is intentionally structured so additional features can be added later.

Potential improvements include:

### 🎮 Better Game Matching

Improve title matching using:

* Fuzzy matching
* Developer/publisher information
* Release year
* Platform
* Genre
* User selection history

---

### 🏷️ More Storefront Information

Display more detailed information such as:

* Store name
* Current price
* Original price
* Discount percentage
* Historical low
* Historical low date
* DRM
* Supported platform
* Purchase URL

---

### 📣 Configurable Notifications

Allow Discord administrators to configure:

* Sale threshold
* Price threshold
* Minimum discount
* Notification channel
* Notification frequency
* Whether historical lows trigger alerts

---

### ⚙️ Discord Commands

Potential commands:

```text
/game
/watch
/unwatch
/price
/history
/watches
/settings
```

For example:

```text
/price R.E.P.O.
```

could immediately return the latest pricing information.

---

### 🌐 Web Dashboard

A future web interface could provide:

* Watched games
* Current prices
* Historical prices
* Store comparisons
* Server configuration
* Notification settings
* Manual price refresh
* Game search

---

### 🛒 Grocery Price Comparison

The same architecture could eventually be expanded into a separate price-comparison application for groceries and other products.

---

# 📝 Development Notes

This project is primarily designed for personal/community use.

It is currently optimized for running locally on a Windows PC, but Python allows it to be moved to another host later if desired.

For local development:

```powershell
.\.venv\Scripts\Activate.ps1
python bot.py
```

---

# 🤝 Contributing

Pull requests and improvements are welcome.

When contributing:

1. Create a branch.
2. Make your changes.
3. Test the bot locally.
4. Verify that secrets are not included.
5. Submit a pull request.

Do not commit:

```text
.env
API keys
Discord tokens
Personal credentials
Local databases
```

---

# ⚠️ Disclaimer

This project is not affiliated with Discord or IsThereAnyDeal.

Game availability, prices, discounts, historical pricing, and storefront information are provided by third-party services and may change at any time.

The bot should be treated as a convenience tool rather than a guaranteed source of pricing information.

Always verify the final price on the retailer's website before purchasing.

---

# 📜 License

Add your preferred license here.

For example:

```text
MIT License
```

If this project is intended to remain private, you may instead choose not to publish a license.

---

# ❤️ Credits

Built with:

* [Discord](https://discord.com/)
* [discord.py](https://github.com/Rapptz/discord.py)
* [IsThereAnyDeal](https://isthereanydeal.com/)
* Python
* SQLite

---

## ⭐ Project Status

**Active Development**

The core functionality is working, including:

* Discord forum monitoring
* Game identification
* Ambiguous title selection
* IsThereAnyDeal integration
* Store price lookup
* Historical low comparison
* Discord deal embeds
* Persistent SQLite watch tracking
* Periodic price monitoring

Additional features and improvements are planned.
