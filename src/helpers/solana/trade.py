import base64
import json
from venv import logger

from jupiter_python_sdk.jupiter import Jupiter

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts

from solders import message
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID

from src.constants import DEFAULT_OPTIONS
from src.helpers.solana.transfer import SolanaTransferHelper


class TradeManager:
    @staticmethod
    async def trade(
        async_client: AsyncClient,
        wallet: Keypair,
        jupiter: Jupiter,
        output_mint: str,
        input_amount: float,
        input_mint: str,
        slippage_bps: int,
    ) -> str:
        """
        Swap tokens using Jupiter Exchange.

        Args:
            agent (SolanaAgentKit): The Solana agent instance.
            output_mint (Pubkey): Target token mint address.
            input_amount (float): Amount to swap (in token decimals).
            input_mint (Pubkey): Source token mint address (default: USDC).
            slippage_bps (int): Slippage tolerance in basis points (default: 300 = 3%).

        Returns:
            str: Transaction signature.

        Raises:
            Exception: If the swap fails.
        """
        # convert wallet.secret() from bytes to string
        input_mint = str(input_mint)
        output_mint = str(output_mint)
        spl_client = AsyncToken(
            async_client, Pubkey.from_string(input_mint), TOKEN_PROGRAM_ID, wallet
        )
        mint = await spl_client.get_mint_info()
        decimals = mint.decimals
        input_amount = int(input_amount * 10**decimals)

        try:
            transaction_data = await jupiter.swap(
                input_mint,
                output_mint,
                input_amount,
                only_direct_routes=False,
                slippage_bps=slippage_bps,
            )
            raw_transaction = VersionedTransaction.from_bytes(
                base64.b64decode(transaction_data)
            )
            signature = wallet.sign_message(
                message.to_bytes_versioned(raw_transaction.message)
            )
            signed_txn = VersionedTransaction.populate(
                raw_transaction.message, [signature]
            )
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(
                txn=bytes(signed_txn), opts=opts
            )
            logger.debug(f"Transaction sent: {json.loads(result.to_json())}")
            transaction_id = json.loads(result.to_json())["result"]
            logger.debug(
                f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}"
            )
            await SolanaTransferHelper._confirm_transaction(async_client, signature)
            return str(signature)

        except Exception as e:
            raise Exception(f"Swap failed: {str(e)}")
