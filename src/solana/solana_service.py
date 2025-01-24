import base64
import json
import math
from typing import Any, Dict
import aiohttp
from nest.core import Injectable
from solders.pubkey import Pubkey
from solana.rpc.commitment import Confirmed
from src.constants import LAMPORTS_PER_SOL
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import (
    get_associated_token_address,
    transfer_checked,
    TransferCheckedParams,
)
import requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from solders.message import MessageV0
from solders.signature import Signature
from src.lib.agent_config import AgentConfig
from src.lib.agent_config.connection_configs.solana import SolanaConfig
from src.lib.base_config import BASE_CONFIG
from src.types import JupiterTokenData
from solders.system_program import TransferParams, transfer


@Injectable
class SolanaService:
    ############### misc ###############
    @staticmethod
    def get_cfg(agent: str) -> SolanaConfig:
        return BASE_CONFIG.get_agent(agent).connections.solana

    ############### reads ###############
    async def get_balance(
        self, cfg: SolanaConfig, token_address: Pubkey | None
    ) -> Dict[str, Any]:
        async_client = cfg.get_client()
        wallet = cfg.get_wallet()
        try:
            if not token_address:
                response = await async_client.get_balance(
                    wallet.pubkey(), commitment=Confirmed
                )
                val = response.value / LAMPORTS_PER_SOL
                return {"balance": val}
            spl_client = AsyncToken(
                async_client, token_address, TOKEN_PROGRAM_ID, wallet
            )

            mint = await spl_client.get_mint_info()
            if not mint.is_initialized:
                raise ValueError("Token mint is not initialized.")

            wallet_ata = get_associated_token_address(wallet.pubkey(), token_address)
            token_balance_resp = await async_client.get_token_account_balance(
                wallet_ata
            )
            if token_balance_resp.value is None:
                return None
            ui_amt = token_balance_resp.value.ui_amount
            if ui_amt is None:
                raise ValueError("Token balance is None.")
            else:
                return {"balance": ui_amt}

        except Exception as error:
            raise Exception(f"Failed to get balance: {str(error)}") from error

    # get price
    async def get_price(self, cfg: SolanaConfig, token_address: str) -> float:
        url = f"https://api.jup.ag/price/v2?ids={token_address}"

        try:
            with requests.get(url) as response:
                response.raise_for_status()
                data = response.json()
                price = data.get("data", {}).get(token_address, {}).get("price")

                if not price:
                    raise Exception("Price data not available for the given token.")

                return float(price)
        except Exception as e:
            raise Exception(f"Price fetch failed: {str(e)}")

    # get tps
    async def get_tps(self, cfg: SolanaConfig) -> float:
        """
        Fetch the current Transactions Per Second (TPS) on the Solana network.

        Args:
            agent: An instance of SolanaAgent providing the RPC connection.

        Returns:
            Current TPS as a float.

        Raises:
            ValueError: If performance samples are unavailable or invalid.
        """
        async_client = cfg.get_client()
        try:
            response = await async_client.get_recent_performance_samples(1)

            performance_samples = response.value
            # logger.debug("Performance Samples:", performance_samples)

            if not performance_samples:
                raise ValueError("No performance samples available.")

            sample = performance_samples[0]

            if (
                not all(
                    hasattr(sample, attr)
                    for attr in ["num_transactions", "sample_period_secs"]
                )
                or sample.num_transactions <= 0
                or sample.sample_period_secs <= 0
            ):
                raise ValueError("Invalid performance sample data.")

            return sample.num_transactions / sample.sample_period_secs

        except Exception as error:
            raise ValueError(f"Failed to fetch TPS: {str(error)}") from error

    # get token data by ticker
    async def get_token_data_by_ticker(
        self, cfg: SolanaConfig, ticker: str
    ) -> dict[str, Any]:

        try:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/search?q={ticker}"
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("pairs"):
                raise Exception("No pairs found for the given ticker.")

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
                return {"address": solana_pairs[0].get("baseToken", {}).get("address")}
            else:
                raise Exception("No pairs found for the given ticker.")
        except Exception as error:
            raise Exception(
                f"Failed to get token data by ticker: {str(error)}"
            ) from error

    # get token data by address
    async def get_token_data_by_address(
        self, cfg: SolanaConfig, address: str
    ) -> JupiterTokenData:

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
            raise Exception("Token not found.")
        except Exception as error:
            raise Exception(f"Error fetching token data: {str(error)}")

    ############### writes ###############
    # transfer
    async def transfer(
        self,
        cfg: SolanaConfig,
        to_address: Pubkey,
        amount: float,
        token_address: Pubkey | None,
    ) -> str:

        try:
            # Convert string address to Pubkey
            to_pubkey = to_address

            if token_address:
                signature = await self._transfer_spl_tokens(
                    to_pubkey,
                    token_address,  # Pass as string, convert inside function
                    amount,
                )
                token_identifier = str(token_address)
            else:
                signature = await self._transfer_native_sol(to_address, amount)
                token_identifier = "SOL"

            await self._confirm_transaction(signature)

            return cfg.format_txid_to_scanner_url(str(signature))

        except Exception as error:
            raise RuntimeError(f"Transfer operation failed: {error}") from error

    # trade
    async def trade(
        self,
        cfg: SolanaConfig,
        output_token_address: Pubkey,
        input_amount: float,
        input_token_address: Pubkey,
        slippage_bps: int,
    ) -> str:

        async_client = cfg.get_client()
        wallet = cfg.get_wallet()
        jupiter = cfg.get_jupiter()
        # convert wallet.secret() from bytes to string
        input_mint = str(input_token_address)
        output_mint = str(output_token_address)
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
                message.to_bytes_versioned(raw_transaction.message)  # type: ignore
            )
            signed_txn = VersionedTransaction.populate(
                raw_transaction.message, [signature]
            )
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(
                txn=bytes(signed_txn), opts=opts
            )
            transaction_id = json.loads(result.to_json())["result"]

            await self._confirm_transaction(signature)
            return cfg.format_txid_to_scanner_url(transaction_id)

        except Exception as e:
            raise Exception(f"Swap failed: {str(e)}")

    # stake
    async def stake(self, cfg: SolanaConfig, amount: float) -> str:

        async_client = cfg.get_client()
        wallet = cfg.get_wallet()
        jupiter = cfg.get_jupiter()
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
                message.to_bytes_versioned(raw_transaction.message)  # type: ignore
            )
            signed_txn = VersionedTransaction.populate(
                raw_transaction.message, [signature]
            )
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(
                txn=bytes(signed_txn), opts=opts
            )
            transaction_id = json.loads(result.to_json())["result"]

            return cfg.format_txid_to_scanner_url(transaction_id)

        except Exception as e:
            raise Exception(f"jupSOL staking failed: {str(e)}")

    # lend
    # async def lend()

    # request faucet
    # async def request_faucet()

    # deploy token
    # async def deploy_token()

    # launch pump fun token
    # async def launch_pump_fun_token()
    async def _transfer_native_sol(
        self,
        async_client: AsyncClient,
        wallet: Keypair,
        to_address: Pubkey,
        amount: float,
    ) -> Signature:
        try:
            # Convert amount to lamports
            lamports = int(amount * LAMPORTS_PER_SOL)

            ix = transfer(
                TransferParams(
                    from_pubkey=wallet.pubkey(),
                    to_pubkey=to_address,
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
            raise Exception(f"Native SOL transfer failed: {str(e)}")

    async def _transfer_spl_tokens(
        self,
        async_client: AsyncClient,
        wallet: Keypair,
        to_address: Pubkey,
        spl_token: Pubkey,
        amount: float,
    ) -> Signature:
        try:
            # Convert string token address to Pubkey
            token_mint = spl_token

            spl_client = AsyncToken(async_client, token_mint, TOKEN_PROGRAM_ID, wallet)

            # Get token decimals
            mint = await spl_client.get_mint_info()
            decimals = mint.decimals

            # Convert amount to token units
            token_amount = math.floor(amount * 10**decimals)

            # Get token accounts
            sender_token_address = get_associated_token_address(
                wallet.pubkey(), token_mint
            )
            recipient_token_address = get_associated_token_address(
                to_address, token_mint
            )

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
            raise Exception(f"SPL token transfer failed: {str(e)}")

    async def _confirm_transaction(
        self, async_client: AsyncClient, signature: Signature
    ) -> None:
        """Wait for transaction confirmation."""
        try:
            await async_client.confirm_transaction(signature, commitment=Confirmed)
        except Exception as e:
            raise Exception(f"Failed to confirm transaction: {str(e)}") from e
