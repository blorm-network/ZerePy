import math
from venv import logger
from src.constants import LAMPORTS_PER_SOL, SOL_FEES

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0  # type: ignore

from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, transfer_checked
from spl.token.instructions import TransferCheckedParams
from solana.transaction import Transaction
import asyncio


class SolanaTransferHelper:
    """Helper class for Solana token and SOL transfers."""

    @staticmethod
    async def transfer(
        async_client: AsyncClient,
        wallet: Keypair,
        to: str,
        amount: float,
        spl_token: str = None,
    ) -> str:
        """
        Transfer SOL or SPL tokens.

        Args:
            async_client: Async RPC client instance.
            wallet: Sender's wallet keypair.
            to: Recipient's public key as string.
            amount: Amount of tokens to transfer.
            spl_token: SPL token mint address as string (default: None).

        Returns:
            Transaction signature.
        """
        try:
            # Convert string address to Pubkey
            to_pubkey = Pubkey.from_string(to)
            
            if spl_token:
                signature = await SolanaTransferHelper._transfer_spl_tokens(
                    async_client,
                    wallet,
                    to_pubkey,
                    spl_token,  # Pass as string, convert inside function
                    amount,
                )
                token_identifier = str(spl_token)
            else:
                signature = await SolanaTransferHelper._transfer_native_sol(
                    async_client, wallet, to_pubkey, amount
                )
                token_identifier = "SOL"
                
            await SolanaTransferHelper._confirm_transaction(async_client, signature)

            logger.debug(
                f"\nSuccess!\n\nSignature: {signature}\nFrom Address: {str(wallet.pubkey())}\nTo Address: {to}\nAmount: {amount}\nToken: {token_identifier}"
            )

            return signature

        except Exception as error:
            logger.error(f"Transfer failed: {error}")
            raise RuntimeError(f"Transfer operation failed: {error}") from error

    @staticmethod
    async def _transfer_native_sol(
        async_client: AsyncClient, wallet: Keypair, to: Pubkey, amount: float
    ) -> str:
        """
        Transfer native SOL.

        Args:
            async_client: AsyncClient instance
            wallet: Sender's keypair
            to: Recipient's Pubkey
            amount: Amount of SOL to transfer

        Returns:
            Transaction signature.
        """
        try:
            # Convert amount to lamports
            lamports = int(amount * LAMPORTS_PER_SOL)
            
            ix = transfer(
                TransferParams(
                    from_pubkey=wallet.pubkey(),
                    to_pubkey=to,
                    lamports=lamports,
                )
            )
            
            blockhash = (await async_client.get_latest_blockhash()).value.blockhash
            msg = MessageV0.try_compile(
                payer=wallet.pubkey(),
                instructions=[ix],
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash,
            )
            tx = VersionedTransaction(msg, [wallet])

            result = await async_client.send_transaction(tx)
            return result.value

        except Exception as e:
            logger.error(f"Native SOL transfer failed: {str(e)}")
            raise

    @staticmethod
    async def _transfer_spl_tokens(
        async_client: AsyncClient,
        wallet: Keypair,
        recipient: Pubkey,
        spl_token: str,
        amount: float,
    ) -> str:
        """
        Transfer SPL tokens from payer to recipient.

        Args:
            async_client: Async RPC client instance.
            wallet: Sender's keypair.
            recipient: Recipient's Pubkey.
            spl_token: SPL token mint address as string.
            amount: Amount of tokens to transfer.

        Returns:
            Transaction signature.
        """
        try:
            # Convert string token address to Pubkey
            token_mint = Pubkey.from_string(spl_token)
            
            spl_client = AsyncToken(
                async_client, token_mint, TOKEN_PROGRAM_ID, wallet.pubkey()
            )
            
            # Get token decimals
            mint = await spl_client.get_mint_info()
            decimals = mint.decimals
            
            # Convert amount to token units
            token_amount = math.floor(amount * 10**decimals)
            
            # Get token accounts
            sender_token_address = get_associated_token_address(wallet.pubkey(), token_mint)
            recipient_token_address = get_associated_token_address(recipient, token_mint)
            
            # Create transfer instruction
            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    source=sender_token_address,
                    dest=recipient_token_address,
                    owner=wallet.pubkey(),
                    mint=token_mint,
                    amount=token_amount,
                    decimals=decimals,
                    program_id=TOKEN_PROGRAM_ID,
                )
            )

            # Build and send transaction
            blockhash = (await async_client.get_latest_blockhash()).value.blockhash
            msg = MessageV0.try_compile(
                payer=wallet.pubkey(),
                instructions=[transfer_ix],
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash,
            )
            tx = VersionedTransaction(msg, [wallet])

            result = await async_client.send_transaction(tx)
            return result.value

        except Exception as e:
            logger.error(f"SPL token transfer failed: {str(e)}")
            raise

    @staticmethod
    async def _confirm_transaction(async_client: AsyncClient, signature: str) -> None:
        """Wait for transaction confirmation."""
        try:
            await async_client.confirm_transaction(signature, commitment=Confirmed)
        except Exception as e:
            logger.error(f"Transaction confirmation failed: {str(e)}")
            raise