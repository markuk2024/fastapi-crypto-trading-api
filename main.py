"""
FastAPI Crypto Trading Signals API
==================================
A production-ready trading system with:
- AI-powered signal generation
- PancakeSwap integration for real trades
- Wallet copy trading
- Performance analytics
- SQLite database for tracking
"""
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import time

# Internal imports
from config import get_settings, Settings
from database import get_db, init_db
from models import Trade, WalletScore, SignalHistory, TokenPrice
from schemas import (
    SignalRequest, SignalResponse, TradeCreate, TradeResponse,
    TradeCloseRequest, TradeExecuteRequest, WalletAnalysisRequest,
    WalletResponse, WalletCopyRequest, PerformanceResponse,
    HistoryFilter, HealthResponse, ConfigUpdate
)
from pancakeswap import trader
from wallet_tracker import wallet_tracker
from ai_scoring import ai_engine

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title="Crypto Trading Signals API",
    description="AI-powered trading signals with PancakeSwap execution and smart wallet copying",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# ============== HEALTH & STATUS ==============

@app.get("/", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """API health check and status."""
    open_trades = db.query(Trade).filter(Trade.status == "OPEN").count()
    
    return HealthResponse(
        status="running",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        testnet_mode=settings.USE_TESTNET,
        copy_trading_enabled=settings.COPY_TRADING_ENABLED,
        active_trades=open_trades
    )


@app.get("/health")
def simple_health():
    """Simple health check for load balancers."""
    return {"status": "healthy"}


# ============== SIGNAL ENDPOINTS ==============

@app.post("/signals", response_model=List[SignalResponse])
def get_signals(
    tokens: List[str],
    use_ai: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get trading signals for multiple tokens.
    
    - **tokens**: List of token symbols (e.g., ["BTC", "ETH", "CAKE"])
    - **use_ai**: Whether to use historical data to improve confidence
    """
    signals = []
    for token in tokens:
        signal = ai_engine.generate_signal(token, db, use_learning=use_ai)
        signals.append(SignalResponse(**signal))
    return signals


@app.get("/signal/{token}", response_model=SignalResponse)
def get_signal(
    token: str,
    use_ai: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get a single trading signal for a token.
    
    - **token**: Token symbol or address
    - **use_ai**: Use historical learning to boost confidence
    """
    signal = ai_engine.generate_signal(token, db, use_learning=use_ai)
    return SignalResponse(**signal)


# ============== TRADE EXECUTION ==============

@app.post("/trade/execute", response_model=TradeResponse)
def execute_trade(
    request: TradeExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a real trade on PancakeSwap.
    
    **WARNING**: This uses real funds if not in testnet mode!
    
    - **token**: Token symbol
    - **token_address**: Contract address (if symbol not recognized)
    - **amount_bnb**: Amount of BNB to swap
    - **slippage**: Slippage tolerance (default 5%)
    """
    if not trader.is_connected():
        raise HTTPException(500, "Blockchain connection failed")
    
    if not trader.account:
        raise HTTPException(400, "No wallet configured. Set PRIVATE_KEY in .env")
    
    # Generate signal first
    signal = ai_engine.generate_signal(request.token, db)
    
    if signal["action"] not in ["BUY", "SELL"]:
        raise HTTPException(400, "Signal is HOLD - no trade executed")
    
    if signal["confidence"] < settings.AI_CONFIDENCE_THRESHOLD:
        raise HTTPException(400, f"Confidence {signal['confidence']} below threshold {settings.AI_CONFIDENCE_THRESHOLD}")
    
    try:
        # Execute real swap
        if signal["action"] == "BUY":
            token_addr = request.token_address or request.token  # In production, resolve symbol to address
            result = trader.buy_token(token_addr, request.amount_bnb, request.slippage)
        else:
            token_addr = request.token_address or request.token
            result = trader.sell_token(token_addr, slippage=request.slippage)
        
        # Record in database
        trade = Trade(
            token=request.token,
            token_address=token_addr,
            action=signal["action"],
            entry_price=signal["price"],
            position_size=request.amount_bnb,
            confidence=signal["confidence"],
            tx_hash=result.get("tx_hash"),
            status="OPEN",
            reason=signal["reason"]
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        return TradeResponse.model_validate(trade)
        
    except Exception as e:
        raise HTTPException(500, f"Trade execution failed: {str(e)}")


@app.post("/trade/simulate", response_model=TradeResponse)
def simulate_trade(
    request: TradeCreate,
    db: Session = Depends(get_db)
):
    """
    Simulate a trade (no real execution - logs to database only).
    Use this for testing before enabling real trades.
    """
    trade = Trade(
        token=request.token,
        token_address=request.token_address,
        action=request.action,
        entry_price=request.entry_price,
        position_size=request.position_size,
        confidence=request.confidence,
        wallet=request.wallet,
        status="OPEN",
        reason="Simulated trade"
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    
    return TradeResponse.model_validate(trade)


@app.post("/trade/close/{trade_id}", response_model=TradeResponse)
def close_trade(
    trade_id: int,
    exit_price: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Close an open trade and calculate PnL.
    
    - **trade_id**: ID of the trade to close
    - **exit_price**: Exit price (if None, uses current market price)
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    
    if not trade:
        raise HTTPException(404, "Trade not found")
    
    if trade.status != "OPEN":
        raise HTTPException(400, f"Trade is already {trade.status}")
    
    # Get exit price
    if exit_price is None:
        # Fetch current price from market
        signal = ai_engine.generate_signal(trade.token, db)
        exit_price = signal["price"]
    
    # Calculate PnL
    if trade.action == "BUY":
        trade.pnl = (exit_price - trade.entry_price) * trade.position_size
    else:  # SELL
        trade.pnl = (trade.entry_price - exit_price) * trade.position_size
    
    trade.exit_price = exit_price
    trade.status = "CLOSED"
    trade.closed_at = datetime.utcnow()
    
    # Update signal history for learning
    signal_record = db.query(SignalHistory).filter(
        SignalHistory.token == trade.token
    ).order_by(SignalHistory.created_at.desc()).first()
    
    if signal_record:
        signal_record.was_profitable = trade.pnl > 0
    
    db.commit()
    db.refresh(trade)
    
    return TradeResponse.model_validate(trade)


# ============== WALLET ANALYTICS & COPY TRADING ==============

@app.get("/wallet/{address}", response_model=WalletResponse)
def analyze_wallet(
    address: str,
    track: bool = False,
    db: Session = Depends(get_db)
):
    """
    Analyze a wallet's performance and optionally track it.
    
    - **address**: BSC wallet address
    - **track**: Add to tracked wallets for copy trading
    """
    # Validate address
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(400, "Invalid BSC address format")
    
    # Get or create wallet score
    wallet_score = db.query(WalletScore).filter(
        WalletScore.wallet_address == address
    ).first()
    
    if not wallet_score:
        # Calculate from trade history
        performance = wallet_tracker.analyze_wallet_performance(address, db)
        
        wallet_score = WalletScore(
            wallet_address=address,
            total_trades=performance["total_trades"],
            winning_trades=performance.get("wins", 0),
            total_pnl=performance["total_pnl"],
            win_rate=performance["win_rate"] / 100 if performance["win_rate"] else 0,
            score=performance["score"],
            is_active=track
        )
        db.add(wallet_score)
        db.commit()
        db.refresh(wallet_score)
    elif track:
        wallet_score.is_active = True
        db.commit()
    
    # Get recent transactions
    recent_txs = wallet_tracker.get_wallet_transactions(address, limit=5)
    
    return WalletResponse(
        address=wallet_score.wallet_address,
        total_trades=wallet_score.total_trades,
        winning_trades=wallet_score.winning_trades,
        total_pnl=wallet_score.total_pnl,
        win_rate=wallet_score.win_rate * 100,
        score=wallet_score.score,
        is_active=wallet_score.is_active,
        last_updated=wallet_score.last_updated,
        recent_transactions=recent_txs
    )


@app.post("/wallet/copy", response_model=TradeResponse)
def copy_wallet_trade(
    request: WalletCopyRequest,
    db: Session = Depends(get_db)
):
    """
    Copy the most recent trade from a tracked wallet.
    
    - **wallet_address**: Address of wallet to copy
    - **amount_bnb**: Amount to trade (default 0.005 BNB)
    - **auto_execute**: Execute immediately (false = simulate only)
    """
    if not settings.COPY_TRADING_ENABLED:
        raise HTTPException(400, "Copy trading is disabled. Enable in settings.")
    
    # Check if wallet is worth copying
    if not wallet_tracker.should_copy_wallet(request.wallet_address, db):
        raise HTTPException(400, "Wallet does not meet copy criteria (poor performance)")
    
    # Detect recent trades
    new_trades = wallet_tracker.get_new_trades(request.wallet_address)
    
    if not new_trades:
        raise HTTPException(404, "No new trades detected from this wallet")
    
    # Get most recent BUY trade
    buy_trades = [t for t in new_trades if t.method == "BUY"]
    if not buy_trades:
        raise HTTPException(404, "No buy trades to copy")
    
    target_trade = buy_trades[0]
    token_symbol = wallet_tracker.format_token_symbol(target_trade.token_out)
    
    # Generate signal with wallet boost
    signal = ai_engine.get_signal_for_wallet_copy(
        request.wallet_address,
        token_symbol,
        db
    )
    
    # Create trade record
    if request.auto_execute:
        # Real execution path
        return execute_trade(
            TradeExecuteRequest(
                token=token_symbol,
                token_address=target_trade.token_out,
                amount_bnb=request.amount_bnb,
                slippage=0.05
            ),
            db
        )
    else:
        # Simulation path
        trade = Trade(
            token=token_symbol,
            token_address=target_trade.token_out,
            action="BUY",
            entry_price=signal["price"],
            position_size=request.amount_bnb,
            confidence=signal["confidence"],
            wallet=request.wallet_address,
            status="OPEN",
            reason=f"Copied from {request.wallet_address[:10]}... | {signal['reason']}"
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return TradeResponse.model_validate(trade)


@app.get("/wallets/top")
def get_top_wallets(
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.5, ge=0, le=1),
    db: Session = Depends(get_db)
):
    """Get top performing wallets for copy trading."""
    wallets = db.query(WalletScore).filter(
        WalletScore.score >= min_score,
        WalletScore.total_trades >= settings.MIN_WALLET_TRADES
    ).order_by(WalletScore.score.desc()).limit(limit).all()
    
    return [
        {
            "address": w.wallet_address,
            "score": w.score,
            "win_rate": w.win_rate * 100,
            "total_trades": w.total_trades,
            "total_pnl": w.total_pnl,
            "is_tracked": w.is_active
        }
        for w in wallets
    ]


# ============== ANALYTICS & PERFORMANCE ==============

@app.get("/performance", response_model=PerformanceResponse)
def get_performance(db: Session = Depends(get_db)):
    """Get overall trading performance metrics."""
    all_trades = db.query(Trade).all()
    open_trades = [t for t in all_trades if t.status == "OPEN"]
    closed_trades = [t for t in all_trades if t.status == "CLOSED"]
    
    if not all_trades:
        return PerformanceResponse(
            total_trades=0,
            open_trades=0,
            closed_trades=0,
            total_pnl=0,
            win_rate=0,
            best_trade_pnl=0,
            worst_trade_pnl=0,
            avg_confidence=0
        )
    
    # Calculate metrics
    total_pnl = sum(t.pnl for t in closed_trades)
    wins = sum(1 for t in closed_trades if t.pnl > 0)
    win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
    
    pnls = [t.pnl for t in closed_trades]
    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0
    
    avg_confidence = sum(t.confidence for t in all_trades) / len(all_trades)
    
    # Group by token
    by_token = {}
    for trade in closed_trades:
        if trade.token not in by_token:
            by_token[trade.token] = {"trades": 0, "pnl": 0, "wins": 0}
        by_token[trade.token]["trades"] += 1
        by_token[trade.token]["pnl"] += trade.pnl
        if trade.pnl > 0:
            by_token[trade.token]["wins"] += 1
    
    token_list = [
        {
            "token": token,
            "trades": data["trades"],
            "pnl": round(data["pnl"], 4),
            "win_rate": round(data["wins"] / data["trades"] * 100, 1)
        }
        for token, data in by_token.items()
    ]
    
    return PerformanceResponse(
        total_trades=len(all_trades),
        open_trades=len(open_trades),
        closed_trades=len(closed_trades),
        total_pnl=round(total_pnl, 4),
        win_rate=round(win_rate, 2),
        best_trade_pnl=round(best_trade, 4),
        worst_trade_pnl=round(worst_trade, 4),
        avg_confidence=round(avg_confidence, 2),
        by_token=sorted(token_list, key=lambda x: x["pnl"], reverse=True)
    )


@app.get("/history")
def get_trade_history(
    token: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    wallet: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get trade history with optional filters."""
    query = db.query(Trade)
    
    if token:
        query = query.filter(Trade.token == token.upper())
    if action:
        query = query.filter(Trade.action == action.upper())
    if status:
        query = query.filter(Trade.status == status.upper())
    if wallet:
        query = query.filter(Trade.wallet == wallet)
    
    total = query.count()
    trades = query.order_by(Trade.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "trades": [TradeResponse.model_validate(t) for t in trades]
    }


@app.get("/history/signals")
def get_signal_history(
    token: Optional[str] = None,
    profitable_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get signal history for AI learning analysis."""
    query = db.query(SignalHistory)
    
    if token:
        query = query.filter(SignalHistory.token == token.upper())
    if profitable_only:
        query = query.filter(SignalHistory.was_profitable == True)
    
    signals = query.order_by(SignalHistory.created_at.desc()).limit(limit).all()
    
    return {
        "total": len(signals),
        "signals": [
            {
                "id": s.id,
                "token": s.token,
                "action": s.action,
                "price": s.price,
                "confidence": s.confidence,
                "rsi": s.rsi,
                "trend": s.trend,
                "was_profitable": s.was_profitable,
                "created_at": s.created_at.isoformat()
            }
            for s in signals
        ]
    }


# ============== CONFIGURATION ==============

@app.get("/config")
def get_config():
    """Get current configuration (sensitive values hidden)."""
    return {
        "testnet_mode": settings.USE_TESTNET,
        "copy_trading_enabled": settings.COPY_TRADING_ENABLED,
        "ai_confidence_threshold": settings.AI_CONFIDENCE_THRESHOLD,
        "max_open_trades": settings.MAX_OPEN_TRADES,
        "risk_per_trade": settings.RISK_PER_TRADE,
        "default_slippage": settings.DEFAULT_SLIPPAGE,
        "learning_enabled": settings.LEARNING_ENABLED,
        "wallet_connected": bool(trader.account),
        "blockchain_connected": trader.is_connected()
    }


@app.post("/config")
def update_config(update: ConfigUpdate):
    """Update runtime configuration (some changes require restart)."""
    # Note: These are runtime-only changes
    # Permanent changes should be made to .env file
    
    if update.copy_trading_enabled is not None:
        settings.COPY_TRADING_ENABLED = update.copy_trading_enabled
    
    if update.ai_confidence_threshold is not None:
        settings.AI_CONFIDENCE_THRESHOLD = update.ai_confidence_threshold
    
    if update.max_open_trades is not None:
        settings.MAX_OPEN_TRADES = update.max_open_trades
    
    return {"status": "updated", "config": get_config()}


# ============== BACKGROUND TASKS ==============

def auto_trading_loop():
    """
    Background task for automated trading.
    Run this as a separate process or thread.
    """
    print("Starting auto trading loop...")
    
    seen_hashes = set()
    
    while settings.COPY_TRADING_ENABLED:
        try:
            # Get active tracked wallets
            from database import SessionLocal
            db = SessionLocal()
            
            try:
                wallets = db.query(WalletScore).filter(
                    WalletScore.is_active == True
                ).all()
                
                for wallet in wallets:
                    new_trades = wallet_tracker.get_new_trades(wallet.wallet_address)
                    
                    for trade in new_trades:
                        if trade.method == "BUY":
                            print(f"New trade detected from {wallet.wallet_address}: {trade.token_out}")
                            # Execute copy trade (with safety limits)
                            # This would call the copy_wallet_trade endpoint
                            
            finally:
                db.close()
            
            time.sleep(settings.WALLET_SCAN_INTERVAL_SECONDS)
            
        except Exception as e:
            print(f"Error in auto trading loop: {e}")
            time.sleep(10)


# Run server directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
