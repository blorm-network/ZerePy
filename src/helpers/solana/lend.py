import base64
import json
import aiohttp
from venv import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts

from solders import message
from solders.keypair import Keypair  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.keypair import Keypair  # type: ignore


class AssetLender:
    @staticmethod
    async def lend_asset(
        async_client: AsyncClient, wallet: Keypair, amount: float
    ) -> str:
        try:
            url = f"https://blink.lulo.fi/actions?amount={amount}&symbol=USDC"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps({"account": str(wallet.pubkey())})

            session = aiohttp.ClientSession()

            async with session.post(url, headers=headers, data=payload) as response:
                if response.status != 200:
                    raise Exception(f"Lulo API Error: {response.status}")
                data = await response.json()
                logger.debug(f"Lending data: {data}")
            transaction_data = base64.b64decode(data["transaction"])
            raw_transaction = VersionedTransaction.from_bytes(transaction_data)
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
            await session.close()
            return str(signature)

        except Exception as e:
            raise Exception(f"Lending failed: {str(e)}")
