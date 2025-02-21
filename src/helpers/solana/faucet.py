from venv import logger

from src.constants import LAMPORTS_PER_SOL

from solana.rpc.commitment import Confirmed
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from solders.keypair import Keypair  # type: ignore


class FaucetManager:
    @staticmethod
    async def request_faucet_funds(async_client: AsyncClient, wallet: Keypair) -> str:
        """
        Request SOL from the Solana faucet (devnet/testnet only).

        Args:
            agent: An object with `connection` (AsyncClient) and `wallet_address` (str).

        Returns:
            str: The transaction signature.

        Raises:
            Exception: If the request fails or times out.
        """
        try:
            logger.debug(f"Requesting faucet for wallet: {repr(wallet.pubkey())}")

            response = await async_client.request_airdrop(
                wallet.pubkey(), 5 * LAMPORTS_PER_SOL
            )

            latest_blockhash = await async_client.get_latest_blockhash()
            await async_client.confirm_transaction(
                response.value,
                commitment=Confirmed,
                last_valid_block_height=latest_blockhash.value.last_valid_block_height,
            )

            logger.debug(f"Airdrop successful, transaction signature: {response.value}")
            return response.value
        except KeyError:
            raise Exception("Airdrop response did not contain a transaction signature.")
        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")
