"""
Configuration management for the Crypto Trading API.
Loads settings from .env file.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./trades.db"
    
    # BSC Configuration
    BSC_RPC_URL: str = "https://bsc-dataseed.binance.org/"
    BSC_TESTNET_RPC: str = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    
    # Wallet (use testnet for development!)
    PRIVATE_KEY: str = ""
    WALLET_ADDRESS: str = ""
    TESTNET_PRIVATE_KEY: str = ""
    TESTNET_WALLET_ADDRESS: str = ""
    USE_TESTNET: bool = True  # Safety flag - always True by default
    
    # Contract Addresses
    PANCAKE_ROUTER_ADDRESS: str = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
    WBNB_ADDRESS: str = "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
    
    # BSCScan
    BSCSCAN_API_KEY: str = ""
    
    # Trading Parameters
    DEFAULT_SLIPPAGE: float = 0.05
    MAX_SLIPPAGE: float = 0.10
    MIN_LIQUIDITY_USD: float = 10000.0
    GAS_PRICE_GWEI: int = 5
    MAX_OPEN_TRADES: int = 3
    RISK_PER_TRADE: float = 0.02
    
    # Copy Trading
    COPY_TRADING_ENABLED: bool = False
    WALLET_SCAN_INTERVAL_SECONDS: int = 30
    MIN_WALLET_WIN_RATE: float = 0.60
    MIN_WALLET_TRADES: int = 5
    
    # AI
    AI_CONFIDENCE_THRESHOLD: float = 0.70
    LEARNING_ENABLED: bool = True
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def active_private_key(self) -> str:
        """Get the active private key based on testnet setting."""
        if self.USE_TESTNET:
            return self.TESTNET_PRIVATE_KEY or self.PRIVATE_KEY
        return self.PRIVATE_KEY
    
    @property
    def active_wallet_address(self) -> str:
        """Get the active wallet address based on testnet setting."""
        if self.USE_TESTNET:
            return self.TESTNET_WALLET_ADDRESS or self.WALLET_ADDRESS
        return self.WALLET_ADDRESS
    
    @property
    def active_rpc_url(self) -> str:
        """Get the active RPC URL based on testnet setting."""
        if self.USE_TESTNET:
            return self.BSC_TESTNET_RPC
        return self.BSC_RPC_URL


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
