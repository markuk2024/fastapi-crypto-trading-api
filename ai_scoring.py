"""
AI scoring system for trading signals.
Combines technical indicators with historical performance learning.
"""
import random
import statistics
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from models import Trade, SignalHistory, TokenPrice
from config import get_settings

settings = get_settings()


@dataclass
class MarketData:
    """Market data for a token."""
    price: float
    price_usd: Optional[float]
    volume_24h: float
    rsi: float
    trend: str  # up, down, sideways
    volatility: float
    support_level: float
    resistance_level: float


class AIScoringEngine:
    """
    AI scoring engine that generates and improves trading signals.
    Uses technical analysis + machine learning from historical data.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.confidence_threshold = self.settings.AI_CONFIDENCE_THRESHOLD
    
    def get_market_data(self, token: str) -> MarketData:
        """
        Fetch market data for a token.
        
        In production, this would:
        - Fetch real price from DEX/PancakeSwap
        - Calculate RSI from price history
        - Get volume from on-chain data
        
        For now, returns simulated data with realistic ranges.
        """
        # Simulate realistic market data
        base_price = random.uniform(0.001, 1000)
        
        return MarketData(
            price=base_price,
            price_usd=base_price * 250,  # Assume BNB price
            volume_24h=random.uniform(10000, 1000000),
            rsi=random.uniform(20, 80),
            trend=random.choice(["up", "down", "sideways"]),
            volatility=random.uniform(0.01, 0.2),
            support_level=base_price * 0.95,
            resistance_level=base_price * 1.05
        )
    
    def calculate_base_score(self, data: MarketData) -> float:
        """
        Calculate base confidence score from technical indicators.
        
        Scoring logic:
        - RSI oversold (<30) = bullish signal (+0.3)
        - RSI overbought (>70) = bearish signal (-0.3)
        - Volume spike = stronger signal (+0.2)
        - Up trend = confirmation (+0.2)
        - High volatility = risk (-0.1)
        """
        score = 0.5  # Neutral starting point
        
        # RSI analysis
        if data.rsi < 30:  # Oversold - potential buy
            score += 0.3
        elif data.rsi > 70:  # Overbought - potential sell
            score -= 0.3
        elif 40 <= data.rsi <= 60:  # Neutral zone
            score += 0.1
        
        # Volume analysis (high volume = more reliable signal)
        if data.volume_24h > 500000:
            score += 0.2
        elif data.volume_24h < 50000:  # Low liquidity = risky
            score -= 0.2
        
        # Trend analysis
        if data.trend == "up":
            score += 0.2
        elif data.trend == "down":
            score -= 0.2
        
        # Volatility penalty (high volatility increases risk)
        if data.volatility > 0.15:
            score -= 0.15
        
        return max(0.0, min(1.0, score))
    
    def improve_confidence_with_history(
        self, 
        token: str, 
        base_confidence: float, 
        db: Session
    ) -> float:
        """
        Adjust confidence based on historical performance of similar signals.
        
        Args:
            token: Token symbol
            base_confidence: Initial confidence from technical analysis
            db: Database session
            
        Returns:
            Adjusted confidence score
        """
        if not self.settings.LEARNING_ENABLED:
            return base_confidence
        
        # Get historical signals for this token
        history = db.query(SignalHistory).filter(
            SignalHistory.token == token,
            SignalHistory.was_profitable.isnot(None)
        ).all()
        
        if len(history) < 3:
            # Not enough data, return base confidence
            return base_confidence
        
        # Calculate historical win rate
        profitable = sum(1 for h in history if h.was_profitable)
        win_rate = profitable / len(history)
        
        # Weighted average: 60% historical, 40% current signal
        adjusted = (win_rate * 0.6) + (base_confidence * 0.4)
        
        return round(max(0.1, min(0.95, adjusted)), 2)
    
    def generate_signal(
        self, 
        token: str, 
        db: Session,
        use_learning: bool = True
    ) -> Dict:
        """
        Generate a trading signal with AI confidence scoring.
        
        Args:
            token: Token symbol or address
            db: Database session
            use_learning: Whether to use historical data
            
        Returns:
            Signal dictionary with action, price, confidence, reasoning
        """
        # Get market data
        data = self.get_market_data(token)
        
        # Calculate base score
        base_confidence = self.calculate_base_score(data)
        
        # Improve with historical data
        if use_learning:
            confidence = self.improve_confidence_with_history(token, base_confidence, db)
        else:
            confidence = base_confidence
        
        # Determine action
        if confidence > 0.7:
            action = "BUY"
        elif confidence < 0.3:
            action = "SELL"
        else:
            action = "HOLD"
        
        # Generate reasoning
        reason = self._generate_reasoning(data, action, confidence)
        
        # Store signal in history
        signal_record = SignalHistory(
            token=token,
            action=action,
            price=data.price,
            confidence=confidence,
            rsi=data.rsi,
            volume_24h=data.volume_24h,
            trend=data.trend
        )
        db.add(signal_record)
        db.commit()
        
        return {
            "token": token.upper(),
            "action": action,
            "price": round(data.price, 6),
            "price_usd": round(data.price_usd, 2) if data.price_usd else None,
            "confidence": round(confidence, 2),
            "reason": reason,
            "indicators": {
                "rsi": round(data.rsi, 2),
                "trend": data.trend,
                "volume_24h": round(data.volume_24h, 2),
                "volatility": round(data.volatility, 3)
            },
            "timestamp": signal_record.created_at.isoformat()
        }
    
    def _generate_reasoning(self, data: MarketData, action: str, confidence: float) -> str:
        """Generate human-readable reasoning for the signal."""
        reasons = []
        
        if data.rsi < 30:
            reasons.append(f"RSI oversold ({data.rsi:.1f})")
        elif data.rsi > 70:
            reasons.append(f"RSI overbought ({data.rsi:.1f})")
        else:
            reasons.append(f"RSI neutral ({data.rsi:.1f})")
        
        if data.volume_24h > 500000:
            reasons.append("High volume")
        elif data.volume_24h < 50000:
            reasons.append("Low volume (caution)")
        
        reasons.append(f"{data.trend} trend")
        
        if confidence > 0.7:
            reasons.append("Strong confidence")
        elif confidence < 0.4:
            reasons.append("Weak signal")
        
        return "; ".join(reasons)
    
    def score_wallet_for_copy_trading(
        self, 
        wallet_address: str, 
        db: Session
    ) -> Dict:
        """
        Calculate a comprehensive score for a wallet's copy-worthiness.
        
        Args:
            wallet_address: Wallet to score
            db: Database session
            
        Returns:
            Score breakdown dictionary
        """
        from models import WalletScore
        
        wallet_data = db.query(WalletScore).filter(
            WalletScore.wallet_address == wallet_address
        ).first()
        
        if not wallet_data:
            return {
                "wallet": wallet_address,
                "score": 0,
                "confidence": 0,
                "recommendation": "INSUFFICIENT_DATA"
            }
        
        # Component scores
        win_rate_score = min(wallet_data.win_rate / 0.7, 1.0)  # Target 70% win rate
        volume_score = min(wallet_data.total_trades / 20, 1.0)  # Target 20+ trades
        profit_score = 1.0 if wallet_data.total_pnl > 0 else 0.5
        
        # Weighted composite
        final_score = (
            win_rate_score * 0.4 +
            volume_score * 0.3 +
            profit_score * 0.3
        )
        
        recommendation = "AVOID"
        if final_score > 0.7 and wallet_data.total_pnl > 0:
            recommendation = "STRONG_COPY"
        elif final_score > 0.5:
            recommendation = "MODERATE_COPY"
        elif final_score > 0.3:
            recommendation = "WEAK_COPY"
        
        return {
            "wallet": wallet_address,
            "score": round(final_score, 2),
            "win_rate_score": round(win_rate_score, 2),
            "volume_score": round(volume_score, 2),
            "profit_score": round(profit_score, 2),
            "raw_win_rate": round(wallet_data.win_rate * 100, 1),
            "total_trades": wallet_data.total_trades,
            "total_pnl": round(wallet_data.total_pnl, 4),
            "recommendation": recommendation
        }
    
    def get_signal_for_wallet_copy(
        self, 
        wallet_address: str, 
        token: str,
        db: Session
    ) -> Dict:
        """
        Generate a signal specifically for copy trading.
        Boosts confidence if wallet has good track record.
        """
        # Get base signal
        signal = self.generate_signal(token, db)
        
        # Get wallet score
        wallet_score = self.score_wallet_for_copy_trading(wallet_address, db)
        
        # Boost confidence based on wallet performance
        original_confidence = signal["confidence"]
        boost = wallet_score["score"] * 0.2  # Up to 20% boost
        signal["confidence"] = min(0.95, original_confidence + boost)
        
        # Add copy trading metadata
        signal["copy_source"] = wallet_address
        signal["wallet_recommendation"] = wallet_score["recommendation"]
        signal["original_confidence"] = original_confidence
        
        return signal


# Singleton instance
ai_engine = AIScoringEngine()
