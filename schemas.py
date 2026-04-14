"""
Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from decimal import Decimal


# ============== Signal Schemas ==============

class SignalRequest(BaseModel):
    """Request to generate a signal for a token."""
    token: str = Field(..., description="Token symbol or address", example="BTC")
    use_ai_learning: bool = Field(default=True, description="Use historical data to improve confidence")


class SignalResponse(BaseModel):
    """Trading signal response."""
    token: str
    action: str = Field(..., description="BUY, SELL, or HOLD")
    price: float
    price_usd: Optional[float] = None
    confidence: float = Field(..., ge=0, le=1, description="AI confidence score 0-1")
    reason: Optional[str] = None
    indicators: Optional[dict] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ============== Trade Schemas ==============

class TradeCreate(BaseModel):
    """Create a new trade."""
    token: str
    token_address: Optional[str] = None
    action: str
    entry_price: float
    position_size: float = Field(default=0.01, description="Amount in BNB to trade")
    confidence: float = 0.5
    wallet: Optional[str] = None  # For copy trading


class TradeResponse(BaseModel):
    """Trade response model."""
    id: int
    token: str
    token_address: Optional[str]
    action: str
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    confidence: float
    pnl: float
    gas_fee: float
    wallet: Optional[str]
    tx_hash: Optional[str]
    status: str
    reason: Optional[str]
    created_at: datetime
    closed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TradeCloseRequest(BaseModel):
    """Request to close a trade."""
    trade_id: int
    exit_price: Optional[float] = None  # If None, will fetch current price


class TradeExecuteRequest(BaseModel):
    """Request to execute a trade with real swap."""
    token: str
    token_address: Optional[str] = None
    amount_bnb: float = Field(default=0.01, ge=0.001, description="BNB amount to swap")
    slippage: float = Field(default=0.05, ge=0.01, le=0.5)


# ============== Wallet Schemas ==============

class WalletAnalysisRequest(BaseModel):
    """Request to analyze a wallet."""
    address: str = Field(..., description="BSC wallet address")
    track: bool = Field(default=False, description="Start tracking this wallet for copy trading")


class WalletResponse(BaseModel):
    """Wallet analytics response."""
    address: str
    total_trades: int
    winning_trades: int
    total_pnl: float
    win_rate: float
    score: float
    is_active: bool
    last_updated: datetime
    recent_transactions: Optional[List[dict]] = None
    
    class Config:
        from_attributes = True


class WalletCopyRequest(BaseModel):
    """Request to copy a wallet's trade."""
    wallet_address: str
    amount_bnb: float = Field(default=0.005, ge=0.001)
    auto_execute: bool = Field(default=False, description="Execute trade immediately")


# ============== Performance Schemas ==============

class PerformanceResponse(BaseModel):
    """Overall trading performance."""
    total_trades: int
    open_trades: int
    closed_trades: int
    total_pnl: float
    total_pnl_usd: Optional[float] = None
    win_rate: float
    avg_trade_duration_minutes: Optional[float] = None
    best_trade_pnl: float
    worst_trade_pnl: float
    avg_confidence: float
    by_token: Optional[List[dict]] = None


class HistoryFilter(BaseModel):
    """Filter for trade history."""
    token: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    wallet: Optional[str] = None
    limit: int = Field(default=100, le=1000)
    offset: int = 0


# ============== System Schemas ==============

class HealthResponse(BaseModel):
    """API health check response."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    testnet_mode: bool
    copy_trading_enabled: bool
    active_trades: int
    
    
class ConfigUpdate(BaseModel):
    """Update runtime configuration."""
    copy_trading_enabled: Optional[bool] = None
    ai_confidence_threshold: Optional[float] = Field(None, ge=0.1, le=0.95)
    max_open_trades: Optional[int] = Field(None, ge=1, le=20)
