from venv import logger
from typing import Dict, Any

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solana.transaction import Transaction

from solders.keypair import Keypair  # type: ignore
from solders.system_program import CreateAccountParams, create_account

from spl.token._layouts import MINT_LAYOUT
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    InitializeMintParams,
    MintToParams,
    create_associated_token_account,
    get_associated_token_address,
    initialize_mint,
    mint_to,
)


class TokenDeploymentManager:
    @staticmethod
    async def deploy_token(
        async_client: AsyncClient, wallet: Keypair, decimals: int = 9
    ) -> Dict[str, Any]:
        """
        Deploy a new SPL token.

        Args:
            agent: SolanaAgentKit instance with wallet and connection.
            decimals: Number of decimals for the token (default: 9).

        Returns:
            A dictionary containing the token mint address.
        """
        try:
            new_mint = Keypair()
            logger.debug(f"Generated mint address: {new_mint.pubkey()}")

            sender = wallet
            client = async_client
            sender_ata = get_associated_token_address(
                sender.pubkey(), new_mint.pubkey()
            )

            transaction = Transaction()

            blockhash = await client.get_latest_blockhash()
            transaction.recent_blockhash = blockhash.value.blockhash

            lamports = (
                await client.get_minimum_balance_for_rent_exemption(
                    MINT_LAYOUT.sizeof()
                )
            ).value

            # Add the create account instruction
            transaction.add(
                create_account(
                    CreateAccountParams(
                        from_pubkey=sender.pubkey(),
                        to_pubkey=new_mint.pubkey(),
                        owner=TOKEN_PROGRAM_ID,
                        lamports=lamports,
                        space=MINT_LAYOUT.sizeof(),
                    )
                )
            )

            transaction.fee_payer = sender.pubkey()

            # Add the initialize mint instruction
            transaction.add(
                initialize_mint(
                    InitializeMintParams(
                        decimals=decimals,
                        freeze_authority=sender.pubkey(),
                        mint=new_mint.pubkey(),
                        mint_authority=sender.pubkey(),
                        program_id=TOKEN_PROGRAM_ID,
                    )
                )
            )

            transaction.add(
                create_associated_token_account(
                    sender.pubkey(), sender.pubkey(), new_mint.pubkey()
                )
            )

            amount_to_transfer = 1000000000 * 10**8
            transaction.add(
                mint_to(
                    MintToParams(
                        amount=amount_to_transfer,
                        dest=sender_ata,
                        mint=new_mint.pubkey(),
                        mint_authority=sender.pubkey(),
                        program_id=TOKEN_PROGRAM_ID,
                        signers=[sender.pubkey(), new_mint.pubkey()],
                    )
                )
            )

            blockhash_response = await async_client.get_latest_blockhash()
            recent_blockhash = blockhash_response.value.blockhash
            transaction.recent_blockhash = recent_blockhash

            transaction.sign_partial(new_mint)
            transaction.sign(sender)

            tx_resp = await async_client.send_raw_transaction(
                transaction.serialize(), opts=TxOpts(preflight_commitment=Confirmed)
            )

            logger.debug(f"resp {tx_resp}")

            tx_id = tx_resp.value

            logger.debug(f"tx_id {tx_id}")

            await async_client.confirm_transaction(
                tx_id,
                commitment=Confirmed,
                last_valid_block_height=blockhash.value.last_valid_block_height,
            )

            logger.debug(f"https://explorer.solana.com/tx/{tx_resp}")

            await client.close()

            logger.debug(f"Transaction Signature: {tx_resp}")

            return {
                "mint": str(new_mint.pubkey()),
                "signature": tx_resp.value,
            }

        except Exception as e:
            logger.error(f"Token deployment failed: {str(e)}")
            raise Exception(f"Token deployment failed: {str(e)}")
