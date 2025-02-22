from typing import Dict
from decimal import Decimal
from web3 import Web3
from web3.types import TxParams, Wei
from eth_typing import Address
from src.constants.abi import ERC20_ABI
import logging

logger = logging.getLogger(__name__)

NATIVE_TOKEN_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

class MachFi:
    def __init__(
        self,
        web3: Web3,
        token_mapping: Dict[str, str],  # Format: {"token_address": "ctoken_address"}
        account: any
    ):
        self.web3 = web3
        self.account = account
        
        # Convert addresses to checksum format
        self.token_mapping = {
            Web3.to_checksum_address(token_addr): Web3.to_checksum_address(ctoken_addr)
            for token_addr, ctoken_addr in token_mapping.items()
        }
        
        # Create reverse mapping for easy token lookup
        self.ctoken_to_token = {v: k for k, v in self.token_mapping.items()}
        
        # Load contract ABIs
        self.ctoken_abi = self._load_ctoken_abi()
        self.erc20_abi = ERC20_ABI
        
        # Initialize contract instances for each token
        self.contracts = {}
        for token_addr, ctoken_addr in self.token_mapping.items():
            self.contracts[token_addr] = {
                'ctoken': self.web3.eth.contract(
                    address=ctoken_addr,
                    abi=self.ctoken_abi
                ),
                'token': self.web3.eth.contract(
                    address=token_addr,
                    abi=self.erc20_abi
                )
            }

    def mint_as_collateral(self, token_address: str, amount: Decimal) -> str:
        """
        Supply assets as collateral to the MachFi protocol.
        
        Args:
            token_address: Address of token to supply
            amount: Amount of token to supply
            
        Returns:
            Transaction hash
        """
        try:
            token_address = Web3.to_checksum_address(token_address)
            if token_address not in self.token_mapping:
                raise ValueError(f"Unsupported token address: {token_address}")

            # If it's native token, return 18 decimals
            if token_address == NATIVE_TOKEN_ADDRESS:
                token_decimals = 18
            else:
                token_decimals = self.contracts[token_address]['token'].functions.decimals().call()

            amount_wei = Wei(int(amount * 10 ** token_decimals))  
            
            ctoken_address = self.token_mapping[token_address]
            contracts = self.contracts[token_address]

            # logger.info(f"token_decimals: {token_decimals}")

            # Only check allowance for non-native tokens
            if token_address != NATIVE_TOKEN_ADDRESS:
                allowance = self.__get_token_allowance(token_address, ctoken_address)
                if allowance < amount_wei:
                    approve_tx = self._approve_tokens_sync(token_address, ctoken_address, amount_wei)
                    logger.info(f"Token approval tx: {approve_tx}")      
            
            # Build mint transaction 
            mint_tx = None
            
            if token_address != NATIVE_TOKEN_ADDRESS:
                mint_tx = self._build_transaction_sync(
                    contracts['ctoken'].functions.mintAsCollateral(amount_wei),
                    value=0
                )
            else:
                mint_tx = self._build_transaction_sync(
                    contracts['ctoken'].functions.mintAsCollateral(),
                    value=amount_wei
                )

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(mint_tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Mint transaction sent: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            raise Exception(f"Mint as collateral failed for token {token_address}: {str(e)}")
        
    def withdraw(self, token_address: str, amount: Decimal) -> str:
        """
        Withdraw supplied assets from the MachFi protocol.
        
        Args:
            token_address: Address of token to withdraw
            amount: Amount of token to withdraw
            
        Returns:
            Transaction hash
        """
        try:
            token_address = Web3.to_checksum_address(token_address)
            if token_address not in self.token_mapping:
                raise ValueError(f"Unsupported token address: {token_address}")
                
            # Get token decimals
            if token_address == NATIVE_TOKEN_ADDRESS:
                token_decimals = 18
            else:
                token_decimals = self.contracts[token_address]['token'].functions.decimals().call()

            amount_wei = Wei(int(amount * 10 ** token_decimals))
            contracts = self.contracts[token_address]

            logger.info(f"amount_wei: {amount_wei}")
            
            # Build redeem transaction            
            withdraw_tx = self._build_transaction_sync(
                contracts['ctoken'].functions.redeemUnderlying(amount_wei),
                value=0
            ) 
            
            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(withdraw_tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Withdraw transaction sent: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            raise Exception(f"Withdraw failed for token {token_address}: {str(e)}")
            
    def __get_token_allowance(self, token_address: str, spender: Address) -> int:
        """Get the allowance of a token for a spender"""
        return self.contracts[token_address]['token'].functions.allowance(self.account.address, spender).call()

    def _approve_tokens_sync(self, token_address: str, spender: Address, amount: Wei) -> str:
        """Synchronous helper method to approve token spending"""
        approve_tx = self._build_transaction_sync(
            self.contracts[token_address]['token'].functions.approve(spender, amount)
        )
        
        signed_tx = self.web3.eth.account.sign_transaction(approve_tx, self.account.key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()

    def _build_transaction_sync(self, contract_func, value: Wei = 0) -> TxParams:
        """Synchronous helper method to build a transaction with proper gas estimation"""
        gas_price = self.web3.eth.gas_price
        nonce = self.web3.eth.get_transaction_count(self.account.address)
        
        tx_params = {
            'from': self.account.address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'value': value,
        }
        
        gas_estimate = contract_func.estimate_gas(tx_params)
        tx_params['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
        
        return contract_func.build_transaction(tx_params)
    


    def _load_ctoken_abi(self) -> list:
        """Load CToken contract ABI"""
        return [
            # Mint function
            { 
                "type":"function",
                "name":"mintAsCollateral",  
                "inputs":[{"name":"mintAmount","type":"uint256","internalType":"uint256"}],
                "outputs":[{"name":"","type":"uint256","internalType":"uint256"}],
                "stateMutability":"nonpayable"
            },
            {"type":"function","name":"mintAsCollateral","inputs":[],"outputs":[{"name":"","type":"uint256","internalType":"uint256"}],"stateMutability":"payable"},
            # Borrow function
            {"type":"function","name":"borrow","inputs":[{"name":"borrowAmount","type":"uint256","internalType":"uint256"}],"outputs":[{"name":"","type":"uint256","internalType":"uint256"}],"stateMutability":"nonpayable"},
            # Repay function
            {"type":"function","name":"repayBorrow","inputs":[{"name":"repayAmount","type":"uint256","internalType":"uint256"}],"outputs":[{"name":"","type":"uint256","internalType":"uint256"}],"stateMutability":"nonpayable"},
            # Redeem function for tokens
            {
                "inputs": [{"internalType": "uint256", "name": "redeemAmount", "type": "uint256"}],
                "name": "redeemUnderlying",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            # Redeem function for native token
            {
                "inputs": [{"internalType": "uint256", "name": "redeemAmount", "type": "uint256"}],
                "name": "redeemUnderlyingNative",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

