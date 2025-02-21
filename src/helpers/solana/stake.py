import base64
import json
import aiohttp
from venv import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solana.rpc.async_api import AsyncClient
from solders import message
from solders.keypair import Keypair  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from solders.keypair import Keypair  # type: ignore


class StakeManager:
    @staticmethod
    async def stake_with_jup(
        async_client: AsyncClient, wallet: Keypair, amount: float
    ) -> str:

        try:

            url = f"https://worker.jup.ag/blinks/swap/So11111111111111111111111111111111111111112/jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v/{amount}"
            payload = {"account": str(wallet.pubkey())}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as res:
                    if res.status != 200:
                        raise Exception(f"Failed to fetch transaction: {res.status}")

                    data = await res.json()

            raw_transaction = VersionedTransaction.from_bytes(
                base64.b64decode(data["transaction"])
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
            transaction_id = json.loads(result.to_json())["result"]
            logger.debug(
                f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}"
            )
            return str(signature)

        except Exception as e:
            raise Exception(f"jupSOL staking failed: {str(e)}")
