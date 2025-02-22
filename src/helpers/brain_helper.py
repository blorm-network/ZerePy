from typing import Dict, Any, Optional, Union
from src.schemas.brain_schemas import (
    BrainResponse, GetBalanceDetails, TokenTransferDetails, 
    TrendingCoinsDetails, ActionType
)
import logging
import os
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

w3 = Web3()
logger = logging.getLogger("connections.brain_helper")

def enhance_goat_params(response: BrainResponse) -> BrainResponse:
    """Enhance parameters based on action type"""
    try:
        if not response.details:
            return response
            
        enhanced_details = None
        if response.action == ActionType.GET_BALANCE:
            enhanced_details = _handle_get_balance_details(response.details.dict())
        elif response.action == ActionType.TRANSFER:
            enhanced_details = _handle_transfer_details(response.details.dict())
        elif response.action == ActionType.GET_TRENDING_COINS:
            enhanced_details = _handle_trending_coins_details(response.details.dict())

        if enhanced_details:
            return BrainResponse(
                note=response.note,
                action=response.action,
                details=enhanced_details
            )
        return response
        
    except Exception as e:
        logger.error(f"Parameter enhancement failed: {e}")
        return BrainResponse(
            note=f"Failed to enhance parameters: {str(e)}",
            action=ActionType.NONE
        )

def _handle_get_balance_details(details: Dict[str, Any]) -> GetBalanceDetails:
    load_dotenv()
    private_key = os.getenv("GOAT_WALLET_PRIVATE_KEY")
    if not private_key:
        raise ValueError("No private key configured")
    account = Account.from_key(private_key)
    return GetBalanceDetails(address=account.address)

def _handle_trending_coins_details(details: Dict[str, Any]) -> TrendingCoinsDetails:
    return TrendingCoinsDetails(
        limit=details.get("limit", 10),
        include_platform=details.get("include_platform", False)
    )

def _handle_transfer_details(details: Dict[str, Any]) -> TokenTransferDetails:
    if not details:
        raise ValueError("Invalid transfer details")

    # Validate addresses
    for field in ["tokenAddress", "to", "from_"]:
        if field in details and details[field]:
            if not w3.is_address(details[field]):
                raise ValueError(f"Invalid address format for {field}")
                
    return TokenTransferDetails(**details)