# imports
from venv import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from src.constants import LAMPORTS_PER_SOL
from src.types import JupiterTokenData

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
import requests

from spl.token.async_client import AsyncToken
from spl.token.instructions import get_associated_token_address
from spl.token.constants import TOKEN_PROGRAM_ID


class SolanaReadHelper:
    @staticmethod
    async def get_balance(
        async_client: AsyncClient,
        wallet: Keypair,
        token_address: str = None,
    ) -> int:
        logger.debug(
            f"Getting balance for {wallet.pubkey()}\ntoken_address: {token_address}"
        )
        try:
            if not token_address:
                response = await async_client.get_balance(
                    wallet.pubkey(), commitment=Confirmed
                )
                return response.value / LAMPORTS_PER_SOL
            token_address = Pubkey.from_string(token_address)
            spl_client = AsyncToken(
                async_client, token_address, TOKEN_PROGRAM_ID, wallet.pubkey()
            )

            mint = await spl_client.get_mint_info()
            if not mint.is_initialized:
                raise ValueError("Token mint is not initialized.")

            wallet_ata = get_associated_token_address(wallet.pubkey(), token_address)
            response = await async_client.get_token_account_balance(wallet_ata)
            if response.value is None:
                return None
            response = response.value.ui_amount
            logger.debug(f"Balance response: {response}")

            return float(response)

        except Exception as error:
            raise Exception(f"Failed to get balance: {str(error)}") from error

    @staticmethod
    def fetch_price(token_address: str) -> float:
        url = f"https://api.jup.ag/price/v2?ids={token_address}"

        try:
            with requests.get(url) as response:
                response.raise_for_status()
                data = response.json()
                price = data.get("data", {}).get(token_address, {}).get("price")

                if not price:
                    raise Exception("Price data not available for the given token.")

                return str(price)
        except Exception as e:
            raise Exception(f"Price fetch failed: {str(e)}")

    @staticmethod
    def get_token_by_ticker(
        ticker: str,
    ) -> str:
        try:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/search?q={ticker}"
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("pairs"):
                return None

            solana_pairs = [
                pair for pair in data["pairs"] if pair.get("chainId") == "solana"
            ]
            solana_pairs.sort(key=lambda x: x.get("fdv", 0), reverse=True)

            solana_pairs = [
                pair
                for pair in solana_pairs
                if pair.get("baseToken", {}).get("symbol", "").lower() == ticker.lower()
            ]

            if solana_pairs:
                return solana_pairs[0].get("baseToken", {}).get("address")
            return None
        except Exception as error:
            logger.error(
                f"Error fetching token address from DexScreener: {str(error)}",
                exc_info=True,
            )
            return None

    @staticmethod
    def get_token_by_address(
        address: str,
    ) -> str:
        try:
            response = requests.get(
                "https://tokens.jup.ag/tokens?tags=verified",
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            for token in data:
                if token.get("address") == str(address):
                    return JupiterTokenData(
                        address=token.get("address"),
                        symbol=token.get("symbol"),
                        name=token.get("name"),
                    )
            return None
        except Exception as error:
            raise Exception(f"Error fetching token data: {str(error)}")
