import json
import aiohttp
from venv import logger
from typing import Dict, Any, List, Optional
from solana.rpc.commitment import Confirmed
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solders import message
from solders.keypair import Keypair  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from src.types import (
    PumpfunTokenOptions,
    TokenLaunchResult,
)
from typing import Any, Dict
from solana.rpc.types import TxOpts
from solders.keypair import Keypair  # type: ignore
from solana.rpc.async_api import AsyncClient


class PumpfunTokenManager:
    @staticmethod
    async def _upload_metadata(
        session: aiohttp.ClientSession,
        token_name: str,
        token_ticker: str,
        description: str,
        image_url: str,
        options: Optional[PumpfunTokenOptions] = None,
    ) -> Dict[str, Any]:
        """
        Uploads token metadata and image to IPFS via Pump.fun.

        Args:
            session: An active aiohttp.ClientSession object
            token_name: Name of the token
            token_ticker: Token symbol/ticker
            description: Token description
            image_url: URL of the token image
            options: Optional token configuration

        Returns:
            A dictionary containing the metadata response from the server.
        """
        logger.debug("Preparing form data for IPFS upload...")
        form_data = aiohttp.FormData()
        form_data.add_field("name", token_name)
        form_data.add_field("symbol", token_ticker)
        form_data.add_field("description", description)
        form_data.add_field("showName", "true")

        if options:
            if options.twitter:
                form_data.add_field("twitter", options.twitter)
            if options.telegram:
                form_data.add_field("telegram", options.telegram)
            if options.website:
                form_data.add_field("website", options.website)

        logger.debug(f"Downloading image from {image_url}...")
        async with session.get(image_url) as image_response:
            logger.debug(f"Image response: {image_response}")
            if image_response.status != 200:
                raise ValueError(
                    f"Failed to download image from {image_url} (status {image_response.status})"
                )
            image_data = await image_response.read()

        form_data.add_field(
            "file", image_data, filename="token_image.png", content_type="image/png"
        )

        logger.debug("Uploading metadata to Pump.fun IPFS endpoint...")
        async with session.post(
            "https://pump.fun/api/ipfs", data=form_data
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"Metadata upload failed (status {response.status}): {error_text}"
                )

            return await response.json()

    @staticmethod
    async def _create_token_transaction(
        session: aiohttp.ClientSession,
        wallet: Keypair,
        mint_keypair: Keypair,
        metadata_response: Dict[str, Any],
        options: Optional[PumpfunTokenOptions] = None,
    ) -> bytes:
        """
        Creates a token transaction via the Pump.fun API.

        Args:
            session: An active aiohttp.ClientSession object
            agent: SolanaAgentKit instance
            mint_keypair: The Keypair for the token mint
            metadata_response: The response from the metadata upload
            options: Optional token configuration

        Returns:
            Serialized transaction bytes.
        """
        options = options or PumpfunTokenOptions()

        payload = {
            "publicKey": str(wallet.pubkey()),
            "action": "create",
            "tokenMetadata": {
                "name": metadata_response["metadata"]["name"],
                "symbol": metadata_response["metadata"]["symbol"],
                "uri": metadata_response["metadataUri"],
            },
            "mint": str(mint_keypair.pubkey()),
            "denominatedInSol": "true",
            "amount": options.initial_liquidity_sol,
            "slippage": options.slippage_bps,
            "priorityFee": options.priority_fee,
            "pool": "pump",
        }

        logger.debug("Requesting token transaction from Pump.fun...")
        async with session.post(
            "https://pumpportal.fun/api/trade-local", json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"Transaction creation failed (status {response.status}): {error_text}"
                )

            tx_data = await response.read()
            return tx_data

    @staticmethod
    async def launch_pumpfun_token(
        async_client: AsyncClient,
        wallet: Keypair,
        token_name: str,
        token_ticker: str,
        description: str,
        image_url: str,
        options: Optional[PumpfunTokenOptions] = None,
    ) -> TokenLaunchResult:
        """
        Launches a new token on Pump.fun.

        Args:
            agent: SolanaAgentKit instance
            token_name: Name of the token
            token_ticker: Token symbol/ticker
            description: Token description
            image_url: URL of the token image
            options: Optional token configuration

        Returns:
            TokenLaunchResult containing the transaction signature, mint address, and metadata URI.
        """
        logger.info("Starting token launch process...")
        mint_keypair = Keypair()
        logger.info(f"Mint public key: {mint_keypair.pubkey()}")
        try:
            # Use a single aiohttp session for both metadata upload and transaction creation
            async with aiohttp.ClientSession() as session:
                logger.info("Uploading metadata to IPFS...")
                metadata_response = await PumpfunTokenManager._upload_metadata(
                    session, token_name, token_ticker, description, image_url, options
                )
                logger.info(f"Metadata response: {metadata_response}")

                logger.info("Creating token transaction...")
                tx_data = await PumpfunTokenManager._create_token_transaction(
                    session, wallet, mint_keypair, metadata_response, options
                )
                logger.info("Deserializing transaction...")
                tx = VersionedTransaction.from_bytes(tx_data)
                logger.info("Signing transaction...")
                signature = wallet.sign_message(message.to_bytes_versioned(tx.message))
                logger.info("Sending transaction to Solana...")
                signed_txn = VersionedTransaction.populate(tx.message, [signature])
                logger.info("Transaction sent!")
                opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
                logger.info("Transaction sent!1")
                result = await async_client.send_transaction(signed_txn, opts=opts)
                logger.info("Transaction sent!2")
                transaction_id = json.loads(result.to_json())["result"]

                logger.info(
                    f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}"
                )
                logger.debug(
                    f'Mint: {str(mint_keypair.pubkey())}\nSignature: {signature}\nMetadata URI: {metadata_response["metadataUri"]}'
                )
                # close the session
                await session.close()

                return True

        except Exception as error:
            logger.error(f"Error in launch_pumpfun_token: {error}")
            raise Exception(f"Token launch failed: {str(error)}") from error
