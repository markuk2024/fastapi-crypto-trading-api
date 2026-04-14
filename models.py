"""
SQLAlchemy models for the trading database.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database import Base


class Trade(Base):
    """Trade record model."""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, index=True, nullable=False)
    token_address = Column(String, nullable=True)
    action = Column(String, nullable=False)  # BUY, SELL, HOLD
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    position_size = Column(Float, default=0.0)  # Amount in BNB/USDT
    confidence = Column(Float, default=0.5)  # AI confidence score
    pnl = Column(Float, default=0.0)  # Profit/Loss
    gas_fee = Column(Float, default=0.0)  # Gas fee in BNB
    wallet = Column(String, nullable=True)  # For copy trading - source wallet
    tx_hash = Column(String, nullable=True)  # Blockchain transaction hash
    status = Column(String, default="OPEN")  # OPEN, CLOSED, PENDING, FAILED
    reason = Column(Text, nullable=True)  # Signal reasoning
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Trade {self.id}: {self.token} {self.action} @ {self.entry_price}>"


class WalletScore(Base):
    """Wallet performance tracking for copy trading."""
    __tablename__ = "wallet_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    score = Column(Float, default=0.0)  # Composite score 0-1
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)  # Whether to copy this wallet
    
    def __repr__(self):
        return f"<WalletScore {self.wallet_address}: {self.score:.2f}>"


class SignalHistory(Base):
    """History of all signals generated (for AI learning)."""
    __tablename__ = "signal_history"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    rsi = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    trend = Column(String, nullable=True)
    was_profitable = Column(Boolean, nullable=True)  # Set later after tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<SignalHistory {self.token} {self.action} @{self.price}>"


class TokenPrice(Base):
    """Cached token prices."""
    __tablename__ = "token_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    price = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
