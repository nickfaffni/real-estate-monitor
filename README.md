# 🏠 Real Estate Monitor for Central Israel

<div align="center">

**Fully autonomous local real estate monitoring system**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Scrapes, analyzes, and notifies you about apartment listings from **Yad2**, **Madlan**, and **Facebook Marketplace**.

</div>

---

## 📋 Table of Contents

- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Features](#-features)
- [Configuration Templates](#-configuration-templates)
- [Telegram Setup](#-telegram-setup)
- [Using the Dashboard](#-using-the-dashboard)
- [How Deal Scoring Works](#-how-deal-scoring-works)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Advanced Features](#️-advanced-features)
- [Pro Tips](#-pro-tips)

---

## 🚀 Quick Start (5 Minutes)

### Step 0: Start Chrome in Debug Mode (Required!)

**IMPORTANT:** The scraper now runs in **Persistent Browser Mode** to handle anti-bot protections. You must start Chrome with remote debugging enabled **before** running the application.

#### macOS Setup

```bash
# Open a new terminal and run this command:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/chrome_bot_profile"
```

#### Linux Setup

```bash
# Open a new terminal and run this command:
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/chrome_bot_profile"
```

#### Windows Setup

```powershell
# Open PowerShell or Command Prompt and run:
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%USERPROFILE%\chrome_bot_profile"
```

**Configuration:** You can customize these settings in your `.env` file:

```bash
CHROME_DEBUG_PORT=9222                    # Change the debug port
CHROME_USER_DATA_DIR=~/chrome_bot_profile # Change the profile directory
HEADLESS=false                            # Set to true for headless mode (not recommended for CAPTCHA)
CAPTCHA_CHECK_INTERVAL=30                 # Seconds between checking if CAPTCHA is solved
CAPTCHA_TIMEOUT_MINUTES=30                # Max wait time for CAPTCHA resolution
SCRAPER_POLLING_INTERVAL=15               # Minutes between scrape runs
```

**What this does:**

- Opens Chrome with remote debugging on port 9222 (configurable via `CHROME_DEBUG_PORT`)
- Uses a separate profile (`chrome_bot_profile`) to avoid conflicts with your regular Chrome
- Allows the scraper to connect to this browser instead of launching new instances
- **Keep this Chrome window open** while the scraper is running

**Benefits:**

- ✅ Manual CAPTCHA solving when needed
- ✅ Browser stays open between scraping runs
- ✅ Better anti-bot evasion
- ✅ Persistent cookies and session
- ✅ Fully configurable via environment variables

### Step 1: Setup (2 minutes)

```bash
# Clone the repository
git clone https://github.com/yourusername/Real-Estate-Monitor.git
cd Real-Estate-Monitor

# Run automated setup
python3 setup_project.py

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Configure (2 minutes)

```bash
# Copy configuration template
cp .env.example .env

# Edit with your preferences
nano .env  # Or: code .env, vim .env
```

**Choose a configuration below and paste into your `.env` file:**

#### 🎓 Student / Budget Rental

```bash
CITIES=תל אביב-יפו
MAX_PRICE=5000
MIN_ROOMS=2
MIN_SIZE_SQM=50
EXCLUDE_GROUND_FLOOR=false
REQUIRE_PARKING=false
```

#### 💼 Young Professional

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים
MAX_PRICE=7000
MIN_ROOMS=2.5
MIN_SIZE_SQM=65
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=2
HIGH_PRIORITY_NEIGHBORHOODS=רמת אביב,בבלי,נווה צדק
```

#### 👨‍👩‍👧‍👦 Family Rental

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים,הרצליה
MAX_PRICE=10000
MIN_ROOMS=3.5
MIN_SIZE_SQM=85
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=1
REQUIRE_PARKING=true
REQUIRE_MAMAD=true
```

#### 🏡 Buying Apartment

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים
MAX_PRICE=2500000
MIN_ROOMS=3
MIN_SIZE_SQM=75
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=2
PREFER_PARKING=true
PREFER_MAMAD=true
```

### Step 3: Run (1 minute)

```bash
python main.py
```

**Open your browser:** [`http://127.0.0.1:8000`](http://127.0.0.1:8000)

### That's It! 🎉

The system is now:

- ✅ Scraping listings every 15 minutes
- ✅ Calculating deal scores
- ✅ Detecting price drops
- ✅ Available via web dashboard

### Monitoring the Application

```bash
# View real-time logs
tail -f real_estate_monitor.log

# Check scraper status
curl http://127.0.0.1:8000/health

# View database statistics
curl http://127.0.0.1:8000/api/db-stats

# View database directly
sqlite3 real_estate.db "SELECT COUNT(*) as total FROM listings;"
sqlite3 real_estate.db "SELECT source, COUNT(*) as count FROM listings GROUP BY source;"
sqlite3 real_estate.db "SELECT city, COUNT(*) as count FROM listings GROUP BY city;"

# Add test data to see the dashboard in action
python add_test_listings.py

# Seed/Update transit stations data from OpenStreetMap
python fetch_stations.py

# Backfill image JSONs for existing Madlan listings
python backfill_images.py
```

### Stopping the Application

```bash
# Press Ctrl+C in the terminal
# The application will shut down gracefully within 5 seconds
# If it takes longer, press Ctrl+C again to force quit
```

---

## 🎯 Features

### Core Functionality

- ✅ **Automated Scraping** from Yad2, Madlan & Facebook Marketplace
- ✅ **Intelligent Deal Scoring** (0-100 based on price, features, recency, and transit proximity)
- ✅ **Transit Proximity Analysis** - Geocodes addresses via Nominatim and resolves proximity to closest heavy rail/subway/light rail/tram station (via OpenStreetMap)
- ✅ **Price Drop Detection** - Automatically re-surfaces good deals
- ✅ **Cross-Site Duplicate Detection** - Avoid seeing the same listing twice
- ✅ **Telegram Notifications** - Get instant alerts for hot deals
- ✅ **Web Dashboard** - Beautiful custom UI to browse and manage listings
- ✅ **Smart Filtering** - Must-have, nice-to-have, and deal-breakers
- ✅ **Neighborhood Analytics** - Compare prices to local averages
- ✅ **24/7 Local Operation** - No cloud, no subscriptions

### Dashboard Features

- 📊 Real-time statistics (new today, high scores)
- 🔍 Advanced filtering (city, neighborhood, transit proximity, score, price)
- ❤️ Like/Hide/Contacted status tracking
- 📈 Price history charts
- 💬 One-click WhatsApp contact
- 🎨 Custom CSS & JavaScript styling (glassmorphism details, transit distance badges)


---

## 📋 Configuration Templates

### All Available Settings

See [`.env.example`](.env.example) for complete configuration options with detailed comments.

### Quick Configurations

#### Rental - Student Budget

```bash
CITIES=תל אביב-יפו
MAX_PRICE=5000
MIN_ROOMS=2
MIN_SIZE_SQM=50
EXCLUDE_GROUND_FLOOR=false
REQUIRE_ELEVATOR_ABOVE_FLOOR=0
REQUIRE_PARKING=false
SCRAPING_INTERVAL_MINUTES=15
```

#### Rental - Young Professional

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים
MAX_PRICE=7000
MIN_ROOMS=2.5
MIN_SIZE_SQM=65
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=2
REQUIRE_PARKING=false
HIGH_PRIORITY_NEIGHBORHOODS=רמת אביב,בבלי,נווה צדק,יד אליהו
PREFER_BALCONY=true
PREFER_PARKING=true
SCRAPING_INTERVAL_MINUTES=15
```

#### Rental - Family (3+ Rooms)

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים,הרצליה,רמת השרון
MAX_PRICE=10000
MIN_ROOMS=3.5
MIN_SIZE_SQM=85
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=1
REQUIRE_PARKING=true
REQUIRE_MAMAD=true
PREFER_BALCONY=true
PREFER_TOP_FLOORS=true
SCRAPING_INTERVAL_MINUTES=15
```

#### Buying - First Apartment

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים
MAX_PRICE=2000000
MIN_ROOMS=2.5
MIN_SIZE_SQM=65
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=2
PREFER_PARKING=true
PREFER_BALCONY=true
PREFER_MAMAD=true
SCRAPING_INTERVAL_MINUTES=20
```

#### Buying - Family Apartment

```bash
CITIES=תל אביב-יפו,רמת גן,גבעתיים,הרצליה,רמת השרון
MAX_PRICE=3500000
MIN_ROOMS=4
MIN_SIZE_SQM=100
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=1
REQUIRE_PARKING=true
REQUIRE_MAMAD=true
PREFER_BALCONY=true
PREFER_TOP_FLOORS=true
SCRAPING_INTERVAL_MINUTES=20
```

---

## 📱 Telegram Setup

Get instant alerts on your phone for hot deals!

### Step-by-Step Setup (3 minutes)

#### 1. Create Telegram Bot

```bash
# On Telegram app:
# 1. Search for @BotFather
# 2. Start a chat and send: /newbot
# 3. Choose a name for your bot (e.g., "My Real Estate Monitor")
# 4. Choose a username (must end in 'bot', e.g., "my_realestate_bot")
# 5. Copy the bot token (looks like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)
```

#### 2. Get Your Chat ID

```bash
# 1. Message your new bot (send any message like "hello")
# 2. Open this URL in your browser (replace <YOUR_BOT_TOKEN>):

https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates

# 3. Look for "chat":{"id":123456789} in the JSON response
# 4. Copy the number (your chat_id)
```

#### 3. Add to Configuration

Edit your `.env` file and add:

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

#### 4. Test Notifications

```bash
# Restart the application
python main.py

# Or test without restarting:
python -c "import asyncio; from app.core.database import init_db; from app.services.telegram_notifier import send_test_notification; from app.core.config import settings; asyncio.run(send_test_notification(init_db(settings.database_url)[1]()))"
```

You should receive a test message! 📱

### Notification Rules

You'll receive notifications when:

1. **New listing** with deal score ≥ 80
2. **New listing** in high-priority neighborhood
3. **Price drop** ≥ 3%

---

## 📊 Using the Dashboard

### Access the Dashboard

Open [`http://127.0.0.1:8000`](http://127.0.0.1:8000) in your browser.

### Main Features

#### 1. View & Filter Listings

- **Filter by**: City, neighborhood, status, minimum score, price range
- **Sort by**: Deal score, price, date
- **Status**: All, Unseen, Liked, Hidden, Contacted

#### 2. Listing Actions

- ❤️ **Like** - Mark as interested
- ❌ **Hide** - Mark as not interested
- 📞 **Contacted** - Mark as contacted
- 👁️ **View** - Open listing on source site
- 💬 **WhatsApp** - Direct contact with seller

#### 3. Statistics Panel

- Total listings in database
- New listings today
- High-score listings (≥80)
- Active filters indicator

#### 4. Listing Details

- Click any listing to see:
  - Full description and images
  - Price history chart
  - Neighborhood price comparison
  - All features and contact info

---

## 🧠 How Deal Scoring Works

Each listing gets a score from 0-100 based on five configurable factors (configurable in `.env` via weights):

### 1. Price Competitiveness (35 points max)

Compared to the neighborhood average price per square meter:

- 30%+ below average = 35 points (100% of weight)
- 20% below average = ~30.6 points
- 10% below average = ~26.25 points
- At average = ~21.8 points
- 10% above average = ~13.1 points
- 20% above average = ~8.75 points
- Worse than 20% above = ~4.4 points

### 2. Features Match (25 points max)

Based on matching your preference settings. Matches are scaled proportionally based on their configuration:

- **Parking** (if preferred)
- **Balcony** (if preferred)
- **Elevator** (if preferred)
- **Mamad / Safe Room** (if preferred)
- **Miklat** (shared building shelter, if preferred and unit lacks Mamad)
- **Top Floor** (if preferred and listing is in top half of floors)

### 3. Recency (15 points max)

How fresh the listing is since first indexed:

- Today: 15 points (100%)
- 1-2 days old: 12 points (80%)
- 3-5 days old: 9 points (60%)
- 6-10 days old: 6 points (40%)
- 11-20 days old: 3 points (20%)
- 20+ days old: 1 point (6.7%)

### 4. Price Trend (15 points max)

Score based on price history changes:

- 10%+ price drop: 15 points (100%)
- 5-10% drop: 12 points (80%)
- 2-5% drop: 9 points (60%)
- Under 2% drop: 7 points (~47%)
- No change: 5 points (~33%)
- Price increase: 2 points (~13%)

### 5. Transit Proximity (10 points max)

Calculated via geocoded coordinates vs. closest public transport station from your `transit_stations.json` data:

- **Station Type Weight**: Heavy Rail / Subway = 1.0, Light Rail / Tram = 0.85
- **Distance Multiplier**:
  - Within 500 meters = 1.0
  - 500m to 1000m = 0.7
  - 1000m to 1500m = 0.4
  - Above 1500m / Not geocoded = 0.0

### Score Interpretation

- **80-100**: 🔥 Excellent deal - Act immediately!
- **60-79**: 👍 Good listing - Worth considering
- **40-59**: 😐 Average - Meets basic criteria
- **Below 40**: 👎 Below expectations

---


## 🧪 Testing

### Quick Start

```bash
# Run all tests with colored output and emojis
pytest tests/

# Run with coverage report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/unit/test_processor.py -v

# Run tests matching a pattern
pytest tests/ -k "deal_score" -v
```

### Test Suite Overview

**169 tests total** - **159 passing** (94% pass rate)

```
tests/
├── conftest.py                    # Shared fixtures & mocks
├── unit/
│   ├── test_processor.py          # Deal scoring & processing (40+ tests)
│   ├── test_parsers.py            # Hebrew parsing (50+ tests)
│   ├── test_duplicate_detector.py # Duplicate detection (12 tests)
│   ├── test_listing_filter.py     # Filtering logic (17 tests)
│   ├── test_config.py             # Configuration (18 tests)
│   └── test_database.py           # Database models (10 tests)
└── mocked_scrapers/
    └── test_yad2_parser.py        # Yad2 scraper (22 tests)
```

### Coverage by Module

- ✅ **100%**: config.py, duplicate_detector.py
- ✅ **98%**: listing_filter.py
- ✅ **93%**: phone_normalizer.py
- ✅ **92%**: database.py
- ✅ **87%**: yad2_scraper.py
- 📊 **37% overall** (services not tested yet)

### Key Features

1. **No Browser Required** - All tests use mocked DrissionPage
2. **Colored Output** - ✅ Green for pass, ❌ Red for fail
3. **Parametrized Tests** - Comprehensive coverage with minimal code
4. **Fast Execution** - ~90 seconds for full suite
5. **CI/CD Ready** - Runs automatically on every push/PR

### GitHub Actions

Tests run automatically on:
- Every push to `main`, `master`, `develop`
- Every pull request
- Python 3.9, 3.10, 3.11 matrix
- Coverage threshold: 35%

### Writing Tests

See [`tests/README.md`](tests/README.md) for detailed examples and best practices.

---

## 📁 Project Structure

```
Real-Estate-Monitor/
├── main.py                    # Application entry point
├── app/                       # Main application package
│   ├── core/                  # Core business logic
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # Database models & ORM
│   │   ├── deal_score.py      # Scoring algorithm
│   │   └── listing_processor.py  # Listing processing
│   ├── services/              # Application services
│   │   ├── scheduler.py       # Job scheduling
│   │   ├── dashboard.py       # Web dashboard (FastAPI)
│   │   └── telegram_notifier.py  # Notifications
│   ├── scrapers/              # Web scrapers
│   │   ├── base_scraper.py    # Base scraper class
│   │   ├── yad2_scraper.py    # Yad2 scraper
│   │   ├── madlan_scraper.py  # Madlan scraper
│   │   └── facebook_scraper.py  # Facebook scraper
│   └── utils/                 # Utility modules
│       ├── phone_normalizer.py   # Phone normalization
│       ├── duplicate_detector.py # Duplicate detection
│       └── listing_filter.py     # Listing filtering
├── templates/                 # HTML templates
│   ├── index.html             # Main dashboard
│   └── listing_detail.html    # Listing detail page
├── .env                       # Your configuration (create from .env.example)
├── .env.example              # Configuration template
├── requirements.txt           # Python dependencies
├── setup_project.py           # Automated setup script
├── test_setup.py              # System tests
└── add_test_listings.py       # Test data generator
```

---

## 🔧 Troubleshooting

### Chrome Connection Failed

If you see an error like "Action Required: Start Chrome with remote debugging port 9222":

```bash
# 1. Make sure Chrome is running with debug mode (macOS):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/chrome_bot_profile"

# 2. Check if the port is in use:
lsof -i :9222

# 3. If you want to use a different port, update .env:
CHROME_DEBUG_PORT=9223
CHROME_USER_DATA_DIR=~/chrome_bot_profile

# Then restart Chrome with the new port (macOS):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9223 \
  --user-data-dir="$HOME/chrome_bot_profile"
```

### CAPTCHA Detected

When the scraper detects a CAPTCHA or anti-bot protection:

1. **Dashboard shows warning banner**: "⚠️ Scraper Paused: CAPTCHA Detected"
2. **Check the open Chrome window**: You'll see the CAPTCHA or security check page
3. **Solve it manually**: Complete the CAPTCHA in the browser
4. **Scraper auto-resumes**: Once solved, scraping continues automatically
5. **Timeout**: If not solved within the configured timeout, the scraper aborts

**Configure CAPTCHA behavior in `.env`:**

```bash
CAPTCHA_CHECK_INTERVAL=30        # How often to check if solved (seconds)
CAPTCHA_TIMEOUT_MINUTES=30       # Maximum wait time before aborting (minutes)
```

**Detected anti-bot systems:**
- PerimeterX
- ShieldSquare
- Cloudflare
- reCAPTCHA
- Hebrew security checks ("אבטחת אתר")

### Application won't start

```bash
# Check Python version (must be 3.9+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Check for errors
tail -f real_estate_monitor.log
```

### Port 8000 already in use

```bash
# Option 1: Change port in .env
DASHBOARD_PORT=8001

# Option 2: Kill process using port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000   # Windows
```

### No listings appearing

```bash
# Check logs for errors
tail -f real_estate_monitor.log

# Verify configuration
cat .env | grep CITIES

# Wait for first scrape (within 15 minutes)
# Or add test data immediately:
python add_test_listings.py
```

### Telegram notifications not working

```bash
# Verify configuration
cat .env | grep TELEGRAM

# Test bot token is valid
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe

# Send test notification
python -c "import asyncio; from app.core.database import init_db; from app.services.telegram_notifier import send_test_notification; from app.core.config import settings; asyncio.run(send_test_notification(init_db(settings.database_url)[1]()))"
```

### Scraper fails

```bash
# Check logs for specific errors
grep ERROR real_estate_monitor.log

# Update Playwright
pip install --upgrade playwright
playwright install chromium

# Test website accessibility
curl -I https://www.yad2.co.il
```

### Application hangs on exit

```bash
# This should be fixed in the latest version
# If still happening, force quit:
# Press Ctrl+C twice
# Or: pkill -f "python main.py"
```

---

## 🛠️ Advanced Features

### Running 24/7

Keep the application running continuously:

```bash
# Using nohup (Linux/macOS)
nohup python main.py > output.log 2>&1 &

# Check if running
ps aux | grep "python main.py"

# Stop it
pkill -f "python main.py"
```

```bash
# Using screen (Linux/macOS)
screen -S real-estate
python main.py
# Press Ctrl+A then D to detach
# Reattach with: screen -r real-estate
```

```bash
# Using systemd (Linux) - Create service file
sudo nano /etc/systemd/system/real-estate-monitor.service

# Add:
[Unit]
Description=Real Estate Monitor
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/Real-Estate-Monitor
ExecStart=/path/to/Real-Estate-Monitor/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable real-estate-monitor
sudo systemctl start real-estate-monitor
sudo systemctl status real-estate-monitor
```

### Database Management

```bash
# Backup database
cp real_estate.db real_estate_backup_$(date +%Y%m%d).db

# Reset database (WARNING: Deletes all data)
rm real_estate.db
python main.py  # Will recreate

# View database with SQLite
sqlite3 real_estate.db
sqlite> SELECT COUNT(*) FROM listings;
sqlite> SELECT city, COUNT(*) FROM listings GROUP BY city;
sqlite> .quit
```

### Custom Scraping Intervals

Edit `.env` to customize scraping frequency:

```bash
SCRAPING_INTERVAL_MINUTES=15      # Global default
YAD2_INTERVAL_MINUTES=15          # Yad2 specific
MADLAN_INTERVAL_MINUTES=15        # Madlan specific
FACEBOOK_INTERVAL_MINUTES=20      # Facebook (slower to avoid rate limits)
```

### Facebook Marketplace Setup

Facebook requires authentication via cookies:

```bash
# 1. Install "Cookie Editor" browser extension (Chrome/Firefox)
# 2. Login to Facebook in your browser
# 3. Click the Cookie Editor extension icon
# 4. Click "Export" and choose "JSON"
# 5. Save the file as facebook_cookies.json in project root
# 6. Restart the application
```

---

## 🎯 Pro Tips

1. **Start Broad**: Begin with wider filters, then narrow down based on results
2. **Monitor Scores**: Adjust preferences in `.env` to match your priorities
3. **Check Daily**: Even automated, check dashboard for new matches
4. **WhatsApp Ready**: Have template messages ready for quick responses
5. **Be Quick**: Good deals go fast - act on high scores (80+) immediately
6. **Use Status Tracking**: Like/Hide listings to keep dashboard organized
7. **Track Price History**: Check price trends before contacting sellers
8. **Set Priority Neighborhoods**: Get notified even for lower scores in favorite areas
9. **Adjust Thresholds**: Lower `MIN_DEAL_SCORE_NOTIFY` if you want more notifications
10. **Review Regularly**: Check hidden listings occasionally - preferences change!

---

## 🔒 Privacy & Ethics

This system is for **personal use only**:

### ✅ Allowed

- Running locally for apartment hunting
- Notifying yourself about listings
- Storing data locally on your computer

### ❌ Not Allowed

- Sharing scraped data publicly
- Selling or commercializing data
- Overloading websites with excessive requests
- Violating terms of service of source websites

**Rate Limiting**: Built-in delays and limits to be respectful to source sites.

---

## 📊 Performance & Requirements

### System Requirements

- **Python**: 3.9 or higher
- **CPU**: Low (< 5% when idle)
- **RAM**: ~200-300 MB
- **Disk**: ~50 MB (database + logs)
- **Network**: Minimal (scraping only)

### Designed For

- **Personal use** on single machine
- **3-5 cities** simultaneous monitoring
- **100-500 listings** in database
- **15-minute** scraping intervals
- **24/7** continuous operation

---

## 🙏 Credits

Built with:

- **Python 3.9+** - Programming language
- **FastAPI** - Web framework
- **Playwright** - Browser automation
- **SQLAlchemy** - Database ORM
- **Bootstrap 5** - UI framework
- **python-telegram-bot** - Notifications
- **APScheduler** - Job scheduling
- **fuzzywuzzy** - Fuzzy string matching

---

## 📝 License

This is personal software for individual use. Not licensed for commercial distribution.

---

## 📞 Support

For issues and questions:

1. **Check logs**: `tail -f real_estate_monitor.log`
2. **Review configuration**: `cat .env`
3. **Run tests**: `python test_setup.py`
4. **Search issues**: [GitHub Issues](https://github.com/yourusername/Real-Estate-Monitor/issues)
5. **Create new issue**: Include logs and configuration (remove sensitive data)

---

<div align="center">

**Happy House Hunting! 🏡**

Made with ❤️ for apartment hunters in Israel

</div>
