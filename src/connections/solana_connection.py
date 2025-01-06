import math
import os
import logging
from typing import Dict, Any, List, Tuple
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair # type: ignore
from dotenv import set_key, load_dotenv
from solders.transaction import Transaction  # type: ignore
from spl.token.async_client import AsyncToken
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
from solders.pubkey import Pubkey  # type: ignore
from typing import Optional
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (get_associated_token_address,
                                    transfer_checked)
LAMPORTS_PER_SOL = 1_000_000_000

logger = logging.getLogger("connections.solana_connection")

class SolanaConnectionError(Exception):
    """Base exception for Solana connection errors"""
    pass

class SolanaConfigurationError(SolanaConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class SolanaRPCError(SolanaConnectionError):
    """Raised when Solana RPC requests fail"""
    pass


class SolanaConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rpc_connection = None
        self.wallet = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Solana configuration from JSON"""
        required_fields = ["rpc"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["rpc"], str):
            raise ValueError("timeline_read_count must be a string")
            
        return config

    def register_actions(self) -> None:
        """Register available Solana actions"""
        self.actions = {
            "send-tokens": Action(
                name="send-tokens",
                parameters=[
                    ActionParameter("to", True, Pubkey, "Solana address to send tokens to"),
                    ActionParameter("amount", True, float, "amount of tokens to send"),
                    ActionParameter("token_address",False,Optional[Pubkey],"token address of tokens to send (None for native SOL)")
                ],
                description="Send tokens to a SOL address from wallet"
            ),
            "swap": Action(
                name="swap-tokens",
                parameters=[
                    ActionParameter("message", True, str, "Text content of the tweet")
                ],ao
                description="Post a new tweet"
            ),
        }
    
    def _get_credentials(self) -> Dict[str, str]:
        """Get Solana credentials from environment with validation"""
        logger.debug("Retrieving Solana credentials")
        load_dotenv()

        required_vars = {
            'SOLANA_PRIVATE_KEY': 'private key',
        }

        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing Solana credentials: {', '.join(missing)}"
            raise SolanaConfigurationError(error_msg)

        logger.debug("All required credentials found")
        return credentials
    def _get_wallet(self) -> Keypair:
        credentials = self._get_credentials()
        self.wallet = Keypair.from_base58_string(credentials['SOLANA_PRIVATE_KEY'])
        return self.wallet
    def _get_rpc_connection(self):
        self.rpc_connection=AsyncClient(self.config["rpc"])
        return self.rpc_connection

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Make a request to the Solana RPC with error handling

        Args:
            method: HTTP method ('get', 'post', etc.)
            endpoint: RPC endpoint path
            **kwargs: Additional request parameters

        Returns:
            Dict containing the RPC response
        """
        logger.debug(f"Making {method.upper()} request to {endpoint}")
        try:
            oauth = self._get_rpc()
            full_url = f"https://api.solana.com/2/{endpoint.lstrip('/')}"

            response = getattr(oauth, method.lower())(full_url, **kwargs)

            if response.status_code not in [200, 201]:
                logger.error(
                    f"Request failed: {response.status_code} - {response.text}"
                )
                raise SolanaRPCError(
                    f"Request failed with status {response.status_code}: {response.text}"
                )

            logger.debug(f"Request successful: {response.status_code}")
            return response.json()

        except Exception as e:
            raise SolanaRPCError(f"RPC request failed: {str(e)}")

    def configure(self) -> None:
        """Sets up Solana RPC authentication"""
        logger.info("Starting Solana wallet setup")

        # Check existing configuration
        if self.is_configured(verbose=False):
            logger.info("Solana RPC is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        setup_instructions = [
            "\n🐦 TWITTER AUTHENTICATION SETUP",
            "\n📝 To get your Solana RPC credentials:",
            "1. Go to https://developer.solana.com/en/portal/dashboard",
            "2. Create a new project and app if you haven't already",
            "3. In your app settings, enable OAuth 1.0a with read and write permissions",
            "4. Get your RPC Key (consumer key) and RPC Key Secret (consumer secret)"
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        try:
            # Get account details
            logger.info("\nPlease enter your Solana RPC credentials:")
            credentials = {
                'consumer_key':
                input("Enter your RPC Key (consumer key): "),
                'consumer_secret':
                input("Enter your RPC Key Secret (consumer secret): ")
            }

            logger.info("Starting OAuth authentication process...")

            # Initialize OAuth flow
            request_token_url = "https://api.solana.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
            oauth = OAuth1Session(credentials['consumer_key'],
                                  client_secret=credentials['consumer_secret'])

            try:
                fetch_response = oauth.fetch_request_token(request_token_url)
            except ValueError as e:
                logger.error("Failed to fetch request token")
                raise SolanaConfigurationError(
                    "Invalid consumer key or secret") from e

            # Get authorization
            base_authorization_url = "https://api.solana.com/oauth/authorize"
            authorization_url = oauth.authorization_url(base_authorization_url)

            auth_instructions = [
                "\n1. Please visit this URL to authorize the application:",
                authorization_url,
                "\n2. After authorizing, Solana will give you a PIN code."
            ]
            logger.info("\n".join(auth_instructions))

            verifier = input("3. Please enter the PIN code here: ")

            # Get access token
            access_token_url = "https://api.solana.com/oauth/access_token"
            oauth = OAuth1Session(
                credentials['consumer_key'],
                client_secret=credentials['consumer_secret'],
                resource_owner_key=fetch_response.get('oauth_token'),
                resource_owner_secret=fetch_response.get('oauth_token_secret'),
                verifier=verifier)

            oauth_tokens = oauth.fetch_access_token(access_token_url)

            # Save credentials
            if not os.path.exists('.env'):
                logger.debug("Creating new .env file")
                with open('.env', 'w') as f:
                    f.write('')

            # Create temporary OAuth session to get user ID
            temp_rpc = OAuth1Session(
                credentials['consumer_key'],
                client_secret=credentials['consumer_secret'],
                resource_owner_key=oauth_tokens.get('oauth_token'),
                resource_owner_secret=oauth_tokens.get('oauth_token_secret'))

            self._rpc_connection = temp_rpc
            user_id, username = self._get_authenticated_user_info()

            # Save to .env
            env_vars = {
                'TWITTER_USER_ID':
                user_id,
                'TWITTER_USERNAME':
                username,
                'TWITTER_CONSUMER_KEY':
                credentials['consumer_key'],
                'TWITTER_CONSUMER_SECRET':
                credentials['consumer_secret'],
                'TWITTER_ACCESS_TOKEN':
                oauth_tokens.get('oauth_token'),
                'TWITTER_ACCESS_TOKEN_SECRET':
                oauth_tokens.get('oauth_token_secret')
            }

            for key, value in env_vars.items():
                set_key('.env', key, value)
                logger.debug(f"Saved {key} to .env")

            logger.info("\n✅ Solana authentication successfully set up!")
            logger.info(
                "Your RPC keys, secrets, and user ID have been stored in the .env file."
            )
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            raise SolanaConfigurationError(error_msg)

   

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Solana action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)

    async def send_tokens(self, to:Pubkey,amount:float,token_address: Optional[Pubkey]) -> dict:
        """send tokens"""
            
        logger.debug(f"Sending tokens\nto: {to}\namount: {amount}\ntoken_address: {token_address}")
        try:
            if token_address:
                sig = await TransferHelper.transfer_tokens(self,to,token_address,amount)
                token = str(token_address)
            else: 
                sig = await TransferHelper.transfer(self,to,amount)
                token = "SOL"
            result = {}
            result['signature']= sig
            result['from_address']= str(self.wallet.pubkey())
            result['to_address']= str(to)
            result['amount']= amount
            result['token']= token
            return result
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise SolanaRPCError(f"Transaction failed: {e}")
class TransferHelper:
    @staticmethod
    async def transfer(conn: SolanaConnection, to: Pubkey,amount:float) -> str:
        if conn.wallet is None:
            conn._get_wallet()
        if conn.rpc_connection is None:
            conn._get_rpc_connection()

        tx = Transaction()
        tx.add(
            Transaction(
                from_pubkey=conn.wallet.pubkey(),
                to_pubkey=to,
                lamports=int(amount * LAMPORTS_PER_SOL)
            )
        )
        tx_res = await conn.rpc_connection.send_transaction(
            tx,
            [conn.wallet],
            opts={
                "skip_preflight": False,
                "preflight_commitment": Confirmed,
                "max_retries":3
            }
        )
        return tx_res.value.signature
    @staticmethod
    async def transfer_tokens(conn: SolanaConnection,to: Pubkey,token_address:Pubkey,amount:float) -> str:
        if conn.wallet is None:
            conn._get_wallet()
        if conn.rpc_connection is None:
            conn._get_rpc_connection()
        spl_client = AsyncToken(conn.rpc_connection, token_address, TOKEN_PROGRAM_ID, conn.wallet.pubkey())
        
        mint = await spl_client.get_mint_info()
        if not mint.is_initialized:
            raise ValueError("Token mint is not initialized.")

        token_decimals = mint.decimals
        if amount < 10 ** -token_decimals:
            raise ValueError("Invalid amount of decimals for the token.")

        tokens = math.floor(amount * (10 ** token_decimals))

        payer_ata = get_associated_token_address(conn.wallet.pubkey(), token_address)
        recipient_ata = get_associated_token_address(to, token_address)

        payer_account_info = await spl_client.get_account_info(payer_ata)
        if not payer_account_info.is_initialized:
            raise ValueError("Payer's associated token account is not initialized.")
        if tokens > payer_account_info.amount:
            raise ValueError("Insufficient funds in payer's token account.")

        recipient_account_info = await spl_client.get_account_info(recipient_ata)
        if not recipient_account_info.is_initialized:
            raise ValueError("Recipient's associated token account is not initialized.")

        transfer_instruction = transfer_checked(
            amount=tokens,
            decimals=token_decimals,
            program_id=TOKEN_PROGRAM_ID,
            owner=conn.wallet.pubkey(),
            source=payer_ata,
            dest=recipient_ata,
            mint=token_address,
        )

        transaction = Transaction().add(transfer_instruction)
        response = await conn.rpc_connection.send_transaction(transaction,
        [conn.wallet],
        opts={
            "skip_preflight": False,
            "preflight_commitment": Confirmed,
            "max_retries": 3
        })

        return response["result"]
    
class SwapHelper:
    @staticmethod
    async def trade(
    conn: SolanaConnection,
    to_token: Pubkey,
    from_amount: float,
    from_token: Pubkey = TOKENS["USDC"],
    slippage_bps: int = DEFAULT_OPTIONS["SLIPPAGE_BPS"],
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
        try:
            quote_url = (
                f"{JUP_API}/quote?"
                f"inputMint={input_mint}"
                f"&outputMint={output_mint}"
                f"&amount={int(input_amount * LAMPORTS_PER_SOL)}"
                f"&slippageBps={slippage_bps}"
                f"&onlyDirectRoutes=true"
                f"&maxAccounts=20"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(quote_url) as quote_response:
                    if quote_response.status != 200:
                        raise Exception(f"Failed to fetch quote: {quote_response.status}")
                    quote_data = await quote_response.json()

                async with session.post(
                    f"{JUP_API}/swap",
                    json={
                        "quoteResponse": quote_data,
                        "userPublicKey": str(agent.wallet_address),
                        "wrapAndUnwrapSol": True,
                        "dynamicComputeUnitLimit": True,
                        "prioritizationFeeLamports": "auto",
                    },
                ) as swap_response:
                    if swap_response.status != 200:
                        raise Exception(af"Failed to fetch swap transaction: {swap_response.status}")
                    swap_data = await swap_response.json()

            swap_transaction_buf = base64.b64decode(swap_data["swapTransaction"])
            transaction = VersionedTransaction.deserialize(swap_transaction_buf)

            latest_blockhash = await agent.connection.get_latest_blockhash()
            transaction.message.recent_blockhash = latest_blockhash.value.blockhash

            transaction.sign([agent.wallet])

            signature = await agent.connection.send_raw_transaction(
                transaction.serialize(), opts={"skip_preflight": False, "max_retries": 3}
            )

            await agent.connection.confirm_transaction(
                signature,
                commitment=Confirmed,
                last_valid_block_height=latest_blockhash.value.last_valid_block_height,
            )

            return str(signature)

        except Exception as e:
            raise Exception(f"Swap failed: {str(e)}")
