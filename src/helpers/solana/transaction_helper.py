from typing import Optional
from solders.transaction import VersionedTransaction
from solders.instruction import CompiledInstruction
from solders.keypair import Keypair
from solders.rpc.responses import GetLatestBlockhashResp
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Processed
from solana.rpc.types import TxOpts
import solders.message
import json
import logging

logger = logging.getLogger("helpers.transaction_helper")

class TransactionHelper:
    @staticmethod
    def encode_number_to_array_le(num: int, array_size: int) -> bytearray:
        result = bytearray(array_size)
        for i in range(array_size):
            result[i] = num & 0xFF
            num >>= 8
        return result

    @staticmethod
    def update_priority_fee(tx: VersionedTransaction, compute_unit_price: int, compute_unit_limit: Optional[int] = None):
        compute_budget_offset = 1

        # Modify compute unit price
        compute_unit_price_data = bytearray(tx.message.instructions[1].data)
        encoded_price = TransactionHelper.encode_number_to_array_le(compute_unit_price, 8)

        for i in range(len(encoded_price)):
            compute_unit_price_data[i + compute_budget_offset] = encoded_price[i]

        # Replace instruction with modified data
        tx.message.instructions[1] = CompiledInstruction(
            program_id_index=tx.message.instructions[1].program_id_index,
            accounts=tx.message.instructions[1].accounts,
            data=bytes(compute_unit_price_data)
        )

        if compute_unit_limit:
            # Modify compute unit limit
            compute_unit_limit_data = bytearray(tx.message.instructions[0].data)
            encoded_limit = TransactionHelper.encode_number_to_array_le(compute_unit_limit, 4)

            for i in range(len(encoded_limit)):
                compute_unit_limit_data[i + compute_budget_offset] = encoded_limit[i]

            # Replace instruction with modified data
            tx.message.instructions[0] = CompiledInstruction(
                program_id_index=tx.message.instructions[0].program_id_index,
                accounts=tx.message.instructions[0].accounts,
                data=bytes(compute_unit_limit_data)
            )

    @staticmethod
    async def send_bridge_transaction(async_client: AsyncClient, wallet: Keypair, transaction: VersionedTransaction, compute_unit_price: int, compute_unit_limit: Optional[int] = None) -> str:
        try:
            # Update priority fee
            TransactionHelper.update_priority_fee(transaction, compute_unit_price, compute_unit_limit)

            # Fetch latest blockhash
            latest_blockhash_resp: GetLatestBlockhashResp = await async_client.get_latest_blockhash(Confirmed)
            latest_blockhash = latest_blockhash_resp.value.blockhash

            # Create message with updated blockhash
            updated_message = solders.message.MessageV0(
                header=transaction.message.header,
                account_keys=transaction.message.account_keys,
                recent_blockhash=latest_blockhash,
                instructions=transaction.message.instructions,
                address_table_lookups=transaction.message.address_table_lookups
            )

            # Sign the message
            signature = wallet.sign_message(
                solders.message.to_bytes_versioned(updated_message)
            )
            logger.info(signature)

            # Create signed transaction with single signature
            signed_tx = VersionedTransaction.populate(
                updated_message, [signature]
            )

            # Send the transaction
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(
                txn=bytes(signed_tx), 
                opts=opts
            )

            # Log and return transaction ID
            transaction_id = json.loads(result.to_json())["result"]
            logger.debug(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")

            # Use signature for confirmation
            await async_client.confirm_transaction(signature, commitment=Confirmed)
            return f"https://explorer.solana.com/tx/{transaction_id}"

        except Exception as e:
            raise ValueError(f"Error sending transaction: {e}")
