"""
Wallet tracking and copy trading functionality.
Uses BSCScan API to monitor smart wallets and decode transactions.
"""
import requests
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from eth_abi import decode
from web3 import Web3
from config import get_settings

settings = get_settings()

# PancakeSwap Router method IDs
SWAP_ETH_FOR_TOKENS = "0x7ff36ab5"  # swapExactETHForTokens
SWAP_TOKENS_FOR_ETH = "0x18cbafe5"  # swapExactTokensForETH


@dataclass
class DecodedSwap:
    """Decoded swap transaction."""
    tx_hash: str
    method: str  # BUY or SELL
    token_in: str
    token_out: str
    amount_in: float
    amount_out_min: float
    to: str
    timestamp: int


class WalletTracker:
    """Track and copy smart wallet trades."""
    
    def __init__(self):
        self.settings = get_settings()
        self.bscscan_api_key = self.settings.BSCSCAN_API_KEY
        self.seen_tx_hashes: set = set()  # Prevent duplicate processing
        self.base_url = "https://api.bscscan.com/api"
    
    def get_wallet_transactions(self, address: str, limit: int = 10) -> List[Dict]:
        """
        Fetch recent transactions for a wallet.
        
        Args:
            address: BSC wallet address
            limit: Number of transactions to fetch
            
        Returns:
            List of transaction dictionaries
        """
        if not self.bscscan_api_key:
            raise ValueError("BSCSCAN_API_KEY not configured")
        
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "sort": "desc",
            "apikey": self.bscscan_api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") != "1":
                return []
            
            txs = data.get("result", [])
            return txs[:limit]
        except Exception as e:
            print(f"Error fetching wallet txs: {e}")
            return []
    
    def decode_swap_input(self, tx_input: str, tx_hash: str = "") -> Optional[DecodedSwap]:
        """
        Decode PancakeSwap router transaction input data.
        
        Args:
            tx_input: Transaction input data (hex string)
            tx_hash: Transaction hash for reference
            
        Returns:
            DecodedSwap object or None if not a swap
        """
        if not tx_input or len(tx_input) < 10:
            return None
        
        method_id = tx_input[:10].lower()
        
        # Decode swapExactETHForTokens (BNB -> Token)
        if method_id == SWAP_ETH_FOR_TOKENS:
            try:
                data = tx_input[10:]
                decoded = decode(
                    ['uint256', 'address[]', 'address', 'uint256'],
                    bytes.fromhex(data)
                )
                
                path = decoded[1]
                if len(path) < 2:
                    return None
                
                return DecodedSwap(
                    tx_hash=tx_hash,
                    method="BUY",
                    token_in=path[0],  # WBNB
                    token_out=path[-1],  # Target token
                    amount_in=0,  # ETH value is in transaction
                    amount_out_min=decoded[0],
                    to=decoded[2],
                    timestamp=0
                )
            except Exception as e:
                return None
        
        # Decode swapExactTokensForETH (Token -> BNB)
        elif method_id == SWAP_TOKENS_FOR_ETH:
            try:
                data = tx_input[10:]
                decoded = decode(
                    ['uint256', 'uint256', 'address[]', 'address', 'uint256'],
                    bytes.fromhex(data)
                )
                
                path = decoded[2]
                if len(path) < 2:
                    return None
                
                return DecodedSwap(
                    tx_hash=tx_hash,
                    method="SELL",
                    token_in=path[0],  # Token being sold
                    token_out=path[-1],  # WBNB
                    amount_in=decoded[0],
                    amount_out_min=decoded[1],
                    to=decoded[3],
                    timestamp=0
                )
            except Exception as e:
                return None
        
        return None
    
    def detect_swaps(self, address: str) -> List[DecodedSwap]:
        """
        Detect PancakeSwap swaps in recent wallet transactions.
        
        Args:
            address: Wallet address to monitor
            
        Returns:
            List of decoded swap transactions
        """
        txs = self.get_wallet_transactions(address)
        swaps = []
        
        for tx in txs:
            tx_hash = tx.get("hash", "")
            to = tx.get("to", "").lower()
            router = self.settings.PANCAKE_ROUTER_ADDRESS.lower()
            
            # Check if transaction is to PancakeSwap router
            if router not in to:
                continue
            
            tx_input = tx.get("input", "")
            decoded = self.decode_swap_input(tx_input, tx_hash)
            
            if decoded:
                decoded.timestamp = int(tx.get("timeStamp", 0))
                swaps.append(decoded)
        
        return swaps
    
    def get_new_trades(self, address: str) -> List[DecodedSwap]:
        """
        Get only new (unseen) trades from a wallet.
        
        Args:
            address: Wallet address
            
        Returns:
            List of new trades not previously seen
        """
        swaps = self.detect_swaps(address)
        new_swaps = []
        
        for swap in swaps:
            if swap.tx_hash not in self.seen_tx_hashes:
                self.seen_tx_hashes.add(swap.tx_hash)
                new_swaps.append(swap)
        
        return new_swaps
    
    def format_token_symbol(self, address: str) -> str:
        """Format token address - in production, this would use a token list."""
        wbnb = self.settings.WBNB_ADDRESS.lower()
        if address.lower() == wbnb:
            return "WBNB"
        return f"{address[:6]}...{address[-4:]}"
    
    def analyze_wallet_performance(self, address: str, db_session) -> Dict:
        """
        Calculate wallet performance score based on stored trade data.
        
        Args:
            address: Wallet address
            db_session: Database session
            
        Returns:
            Performance metrics dictionary
        """
        from models import Trade
        
        trades = db_session.query(Trade).filter(
            Trade.wallet == address,
            Trade.status == "CLOSED"
        ).all()
        
        total = len(trades)
        if total == 0:
            return {
                "address": address,
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "score": 0,
                "is_profitable": False
            }
        
        wins = sum(1 for t in trades if t.pnl > 0)
        total_pnl = sum(t.pnl for t in trades)
        win_rate = wins / total if total > 0 else 0
        
        # Score formula: weighted win rate + profit factor
        profit_factor = min(max(total_pnl / 100, -1), 1)  # Normalize to -1 to 1
        score = (win_rate * 0.7) + (profit_factor * 0.3)
        score = max(0, min(1, score))  # Clamp to 0-1
        
        return {
            "address": address,
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(win_rate * 100, 2),
            "total_pnl": round(total_pnl, 4),
            "score": round(score, 2),
            "is_profitable": total_pnl > 0,
            "avg_pnl_per_trade": round(total_pnl / total, 4) if total > 0 else 0
        }
    
    def should_copy_wallet(self, address: str, db_session) -> bool:
        """
        Determine if a wallet should be copied based on performance.
        
        Args:
            address: Wallet address
            db_session: Database session
            
        Returns:
            True if wallet meets criteria for copying
        """
        performance = self.analyze_wallet_performance(address, db_session)
        
        min_trades = self.settings.MIN_WALLET_TRADES
        min_win_rate = self.settings.MIN_WALLET_WIN_RATE
        
        if performance["total_trades"] < min_trades:
            return False
        
        if performance["win_rate"] < min_win_rate * 100:
            return False
        
        if performance["score"] < 0.5:
            return False
        
        return True
    
    def scan_multiple_wallets(self, addresses: List[str], db_session) -> List[Dict]:
        """
        Scan multiple wallets and return actionable copy signals.
        
        Args:
            addresses: List of wallet addresses
            db_session: Database session
            
        Returns:
            List of copy trade opportunities
        """
        opportunities = []
        
        for address in addresses:
            # Skip if wallet doesn't meet criteria
            if not self.should_copy_wallet(address, db_session):
                continue
            
            # Get new trades from this wallet
            new_trades = self.get_new_trades(address)
            
            for trade in new_trades:
                if trade.method == "BUY":
                    opportunities.append({
                        "wallet": address,
                        "token": trade.token_out,
                        "action": "BUY",
                        "tx_hash": trade.tx_hash,
                        "confidence": 0.85,  # High confidence for proven wallets
                        "timestamp": trade.timestamp
                    })
        
        return opportunities


# Singleton instance
wallet_tracker = WalletTracker()
