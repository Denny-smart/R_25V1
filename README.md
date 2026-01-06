# Deriv Multi-Asset Trading Bot

Professional automated trading bot for Deriv's volatility indices (R_25, R_50, R_75, etc.) using top-down market structure analysis.

[Live Demo & Docs](https://r-25v1.onrender.com/docs/)

## Key Features

- **Multi-Asset Scanning**: Monitors R_25, R_50, R_75 simultaneously.
- **Global Risk Control**: Enforces "1 active trade" limit across all assets to prevent over-leverage.
- **Smart Strategy**: Top-down analysis (Weekly/Daily bias) with structure-based entries.
- **Auto-Recovery**: Detects and manages existing positions on restart.
- **Rich Notifications**: Real-time Telegram alerts with performance tracking.

## Quick Start

### 1. Prerequisites
- Python 3.10+
- [Deriv Account](https://app.deriv.com/account/api-token) (API Token with trading permissions)
- [Supabase Account](https://supabase.com) (For authentication)

### 2. Installation

```bash
git clone https://github.com/yourusername/deriv-r25-trading-bot.git
cd deriv-r25-trading-bot

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the project root:

```env
# Deriv Configuration
DERIV_API_TOKEN=your_token_here
DERIV_APP_ID=1089

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key

# Authentication
ENABLE_AUTHENTICATION=true
INITIAL_ADMIN_EMAIL=your@email.com

# Optional: Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Database Setup

1. Copy the contents of `supabase_setup.sql`.
2. Run it in the [Supabase SQL Editor](https://app.supabase.com/project/_/sql) to create necessary tables and policies.

### 5. Running the Bot

```bash
# Start the server (Development)
uvicorn app.main:app --host 0.0.0.0 --port 10000 --reload
```

- **Dashboard**: http://localhost:10000/
- **API Docs**: http://localhost:10000/docs

## Basic Usage

1.  **Create Admin**: 
    - Register via `/api/v1/auth/register`
    - Or run: `python create_admin.py your@email.com`
2.  **Control**:
    - Use the Dashboard or API to Start/Stop the bot.
    - Monitor Telegram for live trade updates.


## API Reference

### Authentication

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/auth/me` | GET | Get current user info | ✅ |
| `/api/v1/auth/status` | GET | Check auth system status | ❌ |
| `/api/v1/auth/check-approval` | GET | Check user approval status | ⚠️ (Optional) |

### Bot Control

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/bot/start` | POST | Start trading | ✅ |
| `/api/v1/bot/stop` | POST | Stop trading | ✅ |
| `/api/v1/bot/restart` | POST | Restart bot | ✅ |
| `/api/v1/bot/status` | GET | Get current bot status | ✅ |

### Trades & Statistics

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/trades/active` | GET | List active trades | ✅ |
| `/api/v1/trades/history` | GET | Get trade history | ✅ |
| `/api/v1/trades/stats` | GET | Get trading statistics | ✅ |

## Project Structure

```bash
deriv-r25-trading-bot/
├── app/                          # FastAPI application
│   ├── api/                      # REST API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py              # Supabase auth routes (register, login, profile)
│   │   ├── bot.py               # Bot control (start, stop, restart, status)
│   │   ├── trades.py            # Trade history, active trades, statistics
│   │   ├── monitor.py           # Performance monitoring, logs, debug info
│   │   └── config.py            # Configuration management API
│   │
│   ├── bot/                      # Core bot logic
│   │   ├── __init__.py
│   │   ├── runner.py            # Bot lifecycle, multi-asset scanning loop
│   │   ├── state.py             # Global bot state management
│   │   ├── events.py            # Event emission system
│   │   └── telegram_bridge.py   # Bridge between bot and Telegram notifier
│   │
│   ├── core/                     # Core utilities
│   │   ├── __init__.py
│   │   ├── auth.py              # Supabase authentication helpers
│   │   ├── settings.py          # Pydantic settings (from .env)
│   │   ├── supabase.py          # Supabase client initialization
│   │   ├── logging.py           # Structured logging configuration
│   │   └── serializers.py       # JSON serialization helpers
│   │
│   ├── schemas/                  # Pydantic models for validation
│   │   ├── __init__.py
│   │   ├── auth.py              # User, login, register schemas
│   │   ├── bot.py               # Bot status, control schemas
│   │   ├── trades.py            # Trade, signal, statistics schemas
│   │   └── common.py            # Shared response models
│   │
│   ├── ws/                       # WebSocket server
│   │   ├── __init__.py
│   │   └── live.py              # Real-time updates (signals, trades, status)
│   │
│   └── main.py                   # FastAPI app initialization, CORS, routes
│
├── tests/                        # Test suite
│   ├── test_fixes.py            # Integration tests
│   └── verify_notification_calc.py # Verification scripts
│
├── config.py                     # Trading configuration (MAIN CONFIG FILE)
│                                 # - Multi-asset settings (SYMBOLS, ASSET_CONFIG)
│                                 # - Risk parameters (MAX_DAILY_LOSS, MIN_RR_RATIO)
│                                 # - Strategy settings (TOP_DOWN, FIXED modes)
│                                 # - Validation functions
│
├── data_fetcher.py              # Multi-timeframe data fetching
│                                 # - fetch_all_timeframes(): 1w, 1d, 4h, 1h, 5m, 1m
│                                 # - Deriv WebSocket candle streaming
│                                 # - Retry logic and error handling
│
├── strategy.py                  # Top-down market structure analysis
│                                 # - Weekly/Daily bias determination
│                                 # - Level detection (tested, untested, minor)
│                                 # - Entry signal generation (momentum + retest)
│                                 # - Dynamic TP/SL calculation
│
├── trade_engine.py              # Trade execution and monitoring
│                                 # - Contract creation (MULTUP/MULTDOWN)
│                                 # - TP/SL monitoring loop
│                                 # - P&L tracking and trade closure
│                                 # - Portfolio query for startup recovery
│
├── risk_manager.py              # Risk management engine
│                                 # - Global position lock (1 trade max)
│                                 # - Daily loss tracking
│                                 # - Trade frequency limits
│                                 # - Consecutive loss cooldown
│                                 # - Smart startup recovery
│
├── indicators.py                # Technical indicators
│                                 # - RSI, ADX, ATR calculations
│                                 # - Moving averages (SMA, EMA)
│                                 # - Swing high/low detection
│
├── telegram_notifier.py         # Telegram notifications
│                                 # - Rich formatted messages
│                                 # - Signal alerts with strength bars
│                                 # - Trade results with ROI tracking
│                                 # - System status updates
│
├── utils.py                     # Helper functions
│                                 # - Logging utilities
│                                 # - Date/time formatting
│                                 # - Price formatting
│
├── create_admin.py              # Admin user creation script
│                                 # Usage: python create_admin.py user@example.com
│
├── test_telegram.py             # Telegram bot test
├── test_settings.py             # Settings validation test
├── fix_paths.ps1                # Path fixing utility for Windows
│
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (NOT in git)
├── .gitignore                   # Git ignore rules
├── render.yaml                  # Render deployment config
├── supabase_setup.sql           # Supabase database schema
└── README.md                    # Project documentation
```

## License

This project is licensed under the MIT License.

## Support

Contributions, issues, and feature requests are welcome!
Give a ⭐️ if you like this project!

---
*Happy Trading! 🚀*

