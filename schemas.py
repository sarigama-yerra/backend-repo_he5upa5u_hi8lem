"""
Database Schemas for CryptoSleuth

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (e.g., Wallet -> "wallet").
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class Wallet(BaseModel):
    address: str = Field(..., description="Public wallet address")
    chain: Literal["bitcoin", "ethereum", "tron", "polygon", "bsc", "litecoin"] = Field(
        "ethereum", description="Blockchain network"
    )
    entity: Optional[str] = Field(None, description="Known owner or label, if any")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="Computed 0-100 risk score")
    last_scored_at: Optional[datetime] = Field(None, description="When the wallet was last scored")


class Transaction(BaseModel):
    txid: str = Field(..., description="Transaction hash/id")
    from_address: str = Field(..., description="Sender wallet address")
    to_address: str = Field(..., description="Recipient wallet address")
    amount: float = Field(..., ge=0, description="Amount transferred in native units")
    symbol: str = Field(..., description="Asset symbol, e.g., BTC, ETH, USDT")
    timestamp: datetime = Field(..., description="Block time")
    chain: Literal["bitcoin", "ethereum", "tron", "polygon", "bsc", "litecoin"] = Field(
        "ethereum", description="Blockchain network"
    )
    flags: List[str] = Field(default_factory=list, description="Risk flags detected for this tx")


class ThreatIndicator(BaseModel):
    label: str = Field(..., description="Indicator label, e.g., 'Darknet: Hydra'")
    ioc: str = Field(..., description="Wallet address or pattern")
    category: Literal[
        "darknet",
        "mixer",
        "ransomware",
        "scam",
        "sanctioned",
        "exchange",
    ]
    source: str = Field(..., description="Feed source name")
    chain: Optional[str] = Field(None, description="Relevant chain if known")


class Report(BaseModel):
    address: str = Field(..., description="Investigated wallet")
    chain: str = Field("ethereum", description="Blockchain network")
    summary: str = Field(..., description="Narrative summary for law enforcement")
    risk_score: int = Field(..., ge=0, le=100, description="Final risk score")
    details: dict = Field(default_factory=dict, description="Structured details: counts, flags, entities")


# Example baseline to keep database viewer compatibility
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True


class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
