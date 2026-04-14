"""
PancakeSwap DEX integration via Web3.
Handles token swaps, price quotes, and transaction management.
"""
import json
import time
from typing import Optional, Dict, List
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# Web3.py v7 compatibility - middleware is optional
try:
    from web3.middleware.geth_poa import geth_poa_middleware
except ImportError:
    geth_poa_middleware = None
from config import get_settings

settings = get_settings()

# Minimal PancakeSwap Router ABI (swap functions)
ROUTER_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]''')

# ERC20 Token ABI (minimal for approvals)
ERC20_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]''')


class PancakeSwapTrader:
    """PancakeSwap trading interface."""
    
    def __init__(self):
        self.settings = get_settings()
        self.w3 = Web3(Web3.HTTPProvider(self.settings.active_rpc_url))
        if geth_poa_middleware:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.settings.PANCAKE_ROUTER_ADDRESS),
            abi=ROUTER_ABI
        )
        self.wbnb = Web3.to_checksum_address(self.settings.WBNB_ADDRESS)
        
        self.account = None
        if self.settings.active_private_key:
            self.account = Account.from_key(self.settings.active_private_key)
    
    def is_connected(self) -> bool:
        """Check if Web3 connection is working."""
        return self.w3.is_connected()
    
    def get_bnb_balance(self) -> float:
        """Get wallet BNB balance."""
        if not self.account:
            return 0.0
        balance_wei = self.w3.eth.get_balance(self.account.address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_token_balance(self, token_address: str) -> float:
        """Get token balance for the wallet."""
        if not self.account:
            return 0.0
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        balance = token.functions.balanceOf(self.account.address).call()
        decimals = token.functions.decimals().call()
        return balance / (10 ** decimals)
    
    def get_amounts_out(self, amount_in: float, path: List[str]) -> List[int]:
        """Get expected output amounts for a swap."""
        amount_in_wei = self.w3.to_wei(amount_in, 'ether')
        checksum_path = [Web3.to_checksum_address(addr) for addr in path]
        return self.router.functions.getAmountsOut(amount_in_wei, checksum_path).call()
    
    def apply_slippage(self, expected_out: int, slippage: float) -> int:
        """Apply slippage tolerance to expected output."""
        return int(expected_out * (1 - slippage))
    
    def buy_token(
        self, 
        token_address: str, 
        amount_bnb: float, 
        slippage: Optional[float] = None
    ) -> Dict:
        """
        Buy tokens with BNB.
        
        Args:
            token_address: Token contract address
            amount_bnb: Amount of BNB to spend
            slippage: Slippage tolerance (default from settings)
            
        Returns:
            Transaction result with tx_hash, gas_used, etc.
        """
        if not self.account:
            raise ValueError("No wallet configured")
        
        slippage = slippage or self.settings.DEFAULT_SLIPPAGE
        token = Web3.to_checksum_address(token_address)
        
        # Get expected output
        path = [self.wbnb, token]
        amounts = self.get_amounts_out(amount_bnb, path)
        expected_out = amounts[-1]
        amount_out_min = self.apply_slippage(expected_out, slippage)
        
        deadline = int(time.time()) + 60  # 1 minute deadline
        
        # Build transaction
        txn = self.router.functions.swapExactETHForTokens(
            amount_out_min,
            path,
            self.account.address,
            deadline
        ).build_transaction({
            'from': self.account.address,
            'value': self.w3.to_wei(amount_bnb, 'ether'),
            'gas': 300000,
            'gasPrice': self.w3.to_wei(self.settings.GAS_PRICE_GWEI, 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
        })
        
        # Sign and send
        signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.active_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return {
            'tx_hash': self.w3.to_hex(tx_hash),
            'expected_output': expected_out,
            'amount_out_min': amount_out_min,
            'gas_price_gwei': self.settings.GAS_PRICE_GWEI,
            'slippage': slippage,
            'token': token_address,
            'amount_bnb': amount_bnb
        }
    
    def sell_token(
        self,
        token_address: str,
        amount_tokens: Optional[float] = None,
        slippage: Optional[float] = None
    ) -> Dict:
        """
        Sell tokens for BNB.
        
        Args:
            token_address: Token contract address
            amount_tokens: Amount to sell (None = sell all)
            slippage: Slippage tolerance
            
        Returns:
            Transaction result
        """
        if not self.account:
            raise ValueError("No wallet configured")
        
        slippage = slippage or self.settings.DEFAULT_SLIPPAGE
        token = Web3.to_checksum_address(token_address)
        
        # Get token contract
        token_contract = self.w3.eth.contract(address=token, abi=ERC20_ABI)
        decimals = token_contract.functions.decimals().call()
        
        # Determine amount to sell
        if amount_tokens is None:
            balance = token_contract.functions.balanceOf(self.account.address).call()
            amount_in = balance
        else:
            amount_in = int(amount_tokens * (10 ** decimals))
        
        # Approve router if needed
        self._approve_token(token, amount_in)
        
        # Get expected output
        path = [token, self.wbnb]
        amounts = self.router.functions.getAmountsOut(amount_in, path).call()
        expected_out = amounts[-1]
        amount_out_min = self.apply_slippage(expected_out, slippage)
        
        deadline = int(time.time()) + 60
        
        # Build transaction
        txn = self.router.functions.swapExactTokensForETH(
            amount_in,
            amount_out_min,
            path,
            self.account.address,
            deadline
        ).build_transaction({
            'from': self.account.address,
            'gas': 300000,
            'gasPrice': self.w3.to_wei(self.settings.GAS_PRICE_GWEI, 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
        })
        
        # Sign and send
        signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.active_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return {
            'tx_hash': self.w3.to_hex(tx_hash),
            'expected_output_eth': float(self.w3.from_wei(expected_out, 'ether')),
            'amount_out_min': amount_out_min,
            'token': token_address,
            'amount_tokens': amount_in / (10 ** decimals)
        }
    
    def _approve_token(self, token_address: str, amount: int):
        """Approve router to spend tokens."""
        token = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
        
        # Check current allowance
        # Note: In production, check and only approve if needed
        # For simplicity, we approve the exact amount each time
        
        txn = token.functions.approve(
            self.settings.PANCAKE_ROUTER_ADDRESS,
            amount
        ).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei(self.settings.GAS_PRICE_GWEI, 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
        })
        
        signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.active_private_key)
        self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction receipt."""
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                'status': receipt['status'],
                'gas_used': receipt['gasUsed'],
                'block_number': receipt['blockNumber'],
                'confirmations': self.w3.eth.block_number - receipt['blockNumber']
            }
        except Exception as e:
            return None


# Singleton instance
trader = PancakeSwapTrader()
