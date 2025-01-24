from pydantic import ValidationInfo, ValidatorFunctionWrapHandler
from solders.keypair import Keypair


def rpc_validator(
    value: str, handler: ValidatorFunctionWrapHandler, _info: ValidationInfo
) -> str:
    if not value.startswith("http"):
        raise ValueError("RPC URL must start with http")
    return value


def solana_private_key_validator(
    value: str, handler: ValidatorFunctionWrapHandler, _info: ValidationInfo
) -> Keypair:
    if len(value) != 88:
        raise ValueError("Private key must be 88 characters long")
    try:
        keypair = Keypair.from_base58_string(value)
    except Exception as e:
        raise ValueError(f"Invalid private key: {e}")
    return keypair


def blockchain_network_validator(
    value: str, handler: ValidatorFunctionWrapHandler, _info: ValidationInfo
) -> str:
    networks = ["mainnet", "testnet", "regtest"]
    value = value.lower()
    if value not in networks:
        raise ValueError(f"Network {value} not in {networks}")
    return value
