# Crypto Trading Signals API

A production-ready FastAPI-based trading system that generates AI-powered crypto signals, executes trades on PancakeSwap, tracks smart wallets for copy trading, and learns from historical performance.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-00a393.svg)](https://fastapi.tiangolo.com/)
[![Web3.py](https://img.shields.io/badge/Web3.py-6.14+-f16822.svg)](https://web3py.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### Core Trading Engine
- **AI-Powered Signals**: Technical analysis (RSI, volume, trend) + machine learning from historical data
- **Real Trade Execution**: Direct PancakeSwap integration via Web3.py
- **PnL Tracking**: Complete trade lifecycle management with profit/loss calculation
- **Risk Management**: Configurable position sizing, slippage protection, max trade limits

### Copy Trading System
- **Smart Wallet Tracking**: Monitor and analyze successful trader wallets
- **Transaction Decoding**: Decode PancakeSwap router calls to extract exact tokens
- **Performance Scoring**: AI ranks wallets by win rate, PnL, and consistency
- **Auto-Copy**: Automatically mirror trades from top-performing wallets

### Analytics & Learning
- **Performance Dashboard**: Win rates, PnL by token, trade history
- **Signal History**: Database of all signals with profitability tracking
- **Adaptive AI**: Confidence scores improve based on historical accuracy
- **Wallet Leaderboard**: Discover and rank smart money wallets

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Telegram Bot  │────▶│    FastAPI      │────▶│  AI Scoring     │
│   (Optional)    │     │    Endpoints    │     │  Engine         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  PancakeSwap│    │   Wallet    │    │   SQLite    │
    │  Web3 Trader│    │   Tracker   │    │   Database  │
    └─────────────┘    └─────────────┘    └─────────────┘
           │                   │
           ▼                   ▼
    ┌─────────────────┐  ┌─────────────────┐
    │  Binance Smart  │  │  BSCScan API    │
    │  Chain (BSC)    │  │  (Wallet Data)  │
    └─────────────────┘  └─────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/crypto-trading-api.git
cd crypto-trading-api

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Wallet (USE TESTNET KEYS FOR DEVELOPMENT!)
PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here
USE_TESTNET=true  # Always true until you're ready for mainnet

# BSCScan API (for wallet tracking)
BSCSCAN_API_KEY=your_bscscan_api_key_here

# Trading Parameters
DEFAULT_SLIPPAGE=0.05
MAX_OPEN_TRADES=3
AI_CONFIDENCE_THRESHOLD=0.70
```

### 3. Initialize Database

```python
from database import init_db
init_db()
```

### 4. Run the API

```bash
# Development with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000

## API Endpoints

### Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/signals` | Get signals for multiple tokens |
| `GET` | `/signal/{token}` | Get single token signal |

**Example:**
```bash
curl "http://localhost:8000/signal/BTC"
```

**Response:**
```json
{
  "token": "BTC",
  "action": "BUY",
  "price": 43250.50,
  "price_usd": 43250.50,
  "confidence": 0.82,
  "reason": "RSI oversold (28.5); High volume; up trend; Strong confidence",
  "indicators": {
    "rsi": 28.5,
    "trend": "up",
    "volume_24h": 1250000.0,
    "volatility": 0.035
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/trade/execute` | Execute real PancakeSwap trade |
| `POST` | `/trade/simulate` | Simulate trade (no real execution) |
| `POST` | `/trade/close/{trade_id}` | Close open trade |

**Execute Trade:**
```bash
curl -X POST "http://localhost:8000/trade/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "CAKE",
    "token_address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    "amount_bnb": 0.01,
    "slippage": 0.05
  }'
```

### Wallet Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/wallet/{address}` | Analyze wallet performance |
| `POST` | `/wallet/copy` | Copy trade from wallet |
| `GET` | `/wallets/top` | Get top performing wallets |

**Analyze Wallet:**
```bash
curl "http://localhost:8000/wallet/0x123...?track=true"
```

**Response:**
```json
{
  "address": "0x123...",
  "total_trades": 45,
  "winning_trades": 32,
  "total_pnl": 1.245,
  "win_rate": 71.1,
  "score": 0.78,
  "is_active": true,
  "recent_transactions": [...]
}
```

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/performance` | Overall trading statistics |
| `GET` | `/history` | Trade history with filters |
| `GET` | `/history/signals` | Signal history for AI learning |

**Performance Dashboard:**
```bash
curl "http://localhost:8000/performance"
```

**Response:**
```json
{
  "total_trades": 156,
  "open_trades": 3,
  "closed_trades": 153,
  "total_pnl": 2.456,
  "win_rate": 64.7,
  "best_trade_pnl": 0.523,
  "worst_trade_pnl": -0.234,
  "avg_confidence": 0.73,
  "by_token": [
    {"token": "CAKE", "trades": 45, "pnl": 1.234, "win_rate": 68.9},
    {"token": "BNB", "trades": 32, "pnl": 0.876, "win_rate": 62.5}
  ]
}
```

## AI Scoring System

### Confidence Calculation

The AI engine combines multiple factors:

```python
# Base technical analysis (60%)
rsi_score = 0.3 if rsi < 30 else (-0.3 if rsi > 70 else 0)
volume_score = 0.2 if volume > 500k else (-0.2 if volume < 50k else 0)
trend_score = 0.2 if trend == "up" else (-0.2 if trend == "down" else 0)

# Historical learning (40%)
win_rate_from_history = profitable_signals / total_signals

# Final confidence
confidence = (base_score * 0.4) + (historical_score * 0.6)
```

### Adaptive Learning

The system tracks signal outcomes:

```python
# After trade closes
signal.was_profitable = trade.pnl > 0

# Future signals use this data
win_rate = db.query(SignalHistory).filter(
    token == target_token,
    was_profitable == True
).count() / total_signals
```

## Copy Trading Workflow

### 1. Discover Wallets

```bash
# Manually analyze a wallet
curl "http://localhost:8000/wallet/0xSmartMoney123?track=true"
```

### 2. Automatic Scoring

The system calculates:
- **Win Rate**: % of profitable trades
- **Profit Factor**: Total gains / total losses
- **Consistency**: Standard deviation of returns
- **Volume**: Number of trades (minimum 5 for reliability)

### 3. Copy Execution

```bash
# Copy a trade
curl -X POST "http://localhost:8000/wallet/copy" \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "0xSmartMoney123",
    "amount_bnb": 0.005,
    "auto_execute": false
  }'
```

## Safety Features

### Transaction Protection
- **Slippage Control**: Configurable (default 5%, max 10%)
- **Deadline Limits**: 60-second expiration on all swaps
- **Gas Limits**: Prevents excessive gas fees
- **Approval Management**: Automatic token approvals for sells

### Trading Safeguards
```python
# Max open trades limit
if len(active_trades) >= MAX_OPEN_TRADES:
    return {"error": "Max open trades reached"}

# Confidence threshold
if signal["confidence"] < AI_CONFIDENCE_THRESHOLD:
    return {"error": "Confidence too low"}

# Duplicate prevention
if tx_hash in seen_hashes:
    return {"error": "Trade already processed"}
```

### Testnet Mode
Always develop with `USE_TESTNET=true`:
- BSC Testnet RPC: `https://data-seed-prebsc-1-s1.binance.org:8545/`
- Get test BNB from [BSC Testnet Faucet](https://testnet.bnbchain.org/faucet-smart)

## Database Schema

```sql
-- Trades table
trades
  - id: INTEGER PRIMARY KEY
  - token: VARCHAR
  - token_address: VARCHAR
  - action: VARCHAR (BUY/SELL/HOLD)
  - entry_price: FLOAT
  - exit_price: FLOAT
  - position_size: FLOAT
  - confidence: FLOAT
  - pnl: FLOAT
  - tx_hash: VARCHAR
  - status: VARCHAR (OPEN/CLOSED/PENDING)
  - wallet: VARCHAR (for copy trading)
  - created_at: DATETIME
  - closed_at: DATETIME

-- Wallet scores for copy trading
wallet_scores
  - wallet_address: VARCHAR UNIQUE
  - total_trades: INTEGER
  - winning_trades: INTEGER
  - total_pnl: FLOAT
  - win_rate: FLOAT
  - score: FLOAT (0-1 composite)
  - is_active: BOOLEAN

-- Signal history for AI learning
signal_history
  - token: VARCHAR
  - action: VARCHAR
  - price: FLOAT
  - confidence: FLOAT
  - rsi: FLOAT
  - volume_24h: FLOAT
  - trend: VARCHAR
  - was_profitable: BOOLEAN
  - created_at: DATETIME
```

## Project Structure

```
crypto-trading-api/
├── main.py                 # FastAPI application
├── config.py               # Settings management
├── database.py             # SQLAlchemy setup
├── models.py               # Database models
├── schemas.py              # Pydantic schemas
├── pancakeswap.py          # Web3/DEX integration
├── wallet_tracker.py       # Copy trading engine
├── ai_scoring.py           # Signal generation
├── requirements.txt        # Dependencies
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Advanced Usage

### Background Auto-Trading

```python
from main import auto_trading_loop
import threading

# Run in background
thread = threading.Thread(target=auto_trading_loop)
thread.daemon = True
thread.start()
```

### Custom Signal Strategy

```python
from ai_scoring import AIScoringEngine

class MyStrategy(AIScoringEngine):
    def calculate_base_score(self, data):
        # Add custom indicators
        if data.macd_bullish:
            score += 0.25
        return score
```

### Telegram Integration

```python
from python_telegram_bot import Application
from config import settings

async def telegram_signal(update, context):
    token = context.args[0]
    signal = ai_engine.generate_signal(token, db)
    await update.message.reply_text(
        f"🔥 {signal['token']}: {signal['action']}\n"
        f"📊 Confidence: {signal['confidence']}\n"
        f"📝 {signal['reason']}"
    )
```

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t crypto-api .
docker run -p 8000:8000 --env-file .env crypto-api
```

### Railway/Render
1. Push to GitHub
2. Connect repository to [Railway](https://railway.app) or [Render](https://render.com)
3. Add environment variables
4. Deploy

## Security Considerations

⚠️ **IMPORTANT**: This system handles real funds

1. **Never commit private keys**: Use `.env` and `.gitignore`
2. **Use testnet first**: Always validate on testnet
3. **Limit exposure**: Start with small amounts
4. **Monitor gas**: Failed transactions still cost gas
5. **Review contracts**: Verify token contracts before trading

## Roadmap

- [ ] Real-time WebSocket price feeds
- [ ] Multi-chain support (ETH, Arbitrum, Polygon)
- [ ] Mempool sniping (pre-confirmation trades)
- [ ] ML model training on historical data
- [ ] Telegram bot commands
- [ ] Web dashboard (React frontend)
- [ ] Paper trading mode
- [ ] Risk management (Kelly criterion, position sizing)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file

## Disclaimer

**Trading cryptocurrency carries significant risk of loss. This software is for educational purposes only. Never trade with funds you cannot afford to lose. Past performance does not guarantee future results.**

## Contact

- GitHub: [@yourusername](https://github.com/yourusername)
- Twitter: [@yourhandle](https://twitter.com/yourhandle)
- Email: your.email@example.com

---

Built with ❤️ using FastAPI, Web3.py, and lots of ☕
