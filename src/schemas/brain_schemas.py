from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    NONE = "none"
    GET_ADDRESS = "get_address"
    GET_CHAIN = "get_chain"
    GET_BALANCE = "get_balance"
    GET_COIN_PRICE = "get_coin_price"
    GET_TRENDING_COINS = "get_trending_coins"
    SEARCH_COINS = "search_coins"
    APPROVE = "approve"
    CONVERT_FROM_BASE_UNIT = "convert_from_base_unit"
    CONVERT_TO_BASE_UNIT = "convert_to_base_unit"
    GET_TOKEN_ALLOWANCE = "get_token_allowance"
    GET_TOKEN_BALANCE = "get_token_balance"
    GET_TOKEN_INFO = "get_token_info_by_symbol"
    GET_TOKEN_SUPPLY = "get_token_total_supply"
    TRANSFER = "transfer"
    TRANSFER_FROM = "transfer_from"

class GetBalanceDetails(BaseModel):
    address: str = Field(description="The address to get the balance of")

class CoinPriceDetails(BaseModel):
    coin_id: str = Field(description="The ID of the coin on CoinGecko")
    vs_currency: str = Field(default="usd", description="The target currency for price")
    include_market_cap: bool = Field(default=True)
    include_24hr_vol: bool = Field(default=True)
    include_24hr_change: bool = Field(default=True)
    include_last_updated_at: bool = Field(default=True)

class TrendingCoinsDetails(BaseModel):
    limit: Optional[int] = Field(default=10, description="Number of trending coins to return")
    include_platform: Optional[bool] = Field(default=False, description="Include platform contract addresses")

class SearchCoinsDetails(BaseModel):
    query: str = Field(description="The search query to find coins")
    exact_match: bool = Field(description="Only return exact matches")

class ApproveDetails(BaseModel):
    tokenAddress: str = Field(description="Token contract address")
    spender: str = Field(description="Address to approve")
    amount: str = Field(description="Amount to approve in base units")

class ConvertUnitDetails(BaseModel):
    amount: str = Field(description="Amount to convert")
    decimals: int = Field(description="Token decimals")

class TokenAllowanceDetails(BaseModel):
    tokenAddress: str = Field(description="Token contract address")
    owner: str = Field(description="Token owner address")
    spender: str = Field(description="Spender address")

class TokenBalanceDetails(BaseModel):
    wallet: str = Field(description="Wallet address")
    tokenAddress: str = Field(description="Token contract address")

class TokenInfoDetails(BaseModel):
    symbol: str = Field(description="Token symbol")

class TokenTransferDetails(BaseModel):
    tokenAddress: str = Field(description="Token contract address")
    to: str = Field(description="Recipient address")
    amount: str = Field(description="Amount in base units")

class TransferFromDetails(BaseModel):
    tokenAddress: str = Field(description="Token contract address")
    from_: str = Field(description="Sender address")
    to: str = Field(description="Recipient address")
    amount: str = Field(description="Amount in base units")

class BrainResponse(BaseModel):
    note: str = Field(description="User-friendly response message")
    action: ActionType
    details: Optional[Union[
        GetBalanceDetails,
        CoinPriceDetails,
        TrendingCoinsDetails,
        SearchCoinsDetails,
        ApproveDetails,
        ConvertUnitDetails,
        TokenAllowanceDetails,
        TokenBalanceDetails,
        TokenInfoDetails,
        TokenTransferDetails,
        TransferFromDetails
    ]] = None