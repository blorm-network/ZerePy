from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import asyncio
import signal
import json
import threading
import hashlib
import os
import uuid
import base58
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv
from dstack_sdk import AsyncTappdClient, DeriveKeyResponse, TdxQuoteResponse
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from src.cli import ZerePyCLI

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("server/app")

# Load environment variables
load_dotenv()
DSTACK_SIMULATOR_ENDPOINT = os.getenv("DSTACK_SIMULATOR_ENDPOINT")

# Initialize environment variables for wallet
os.environ["GOAT_WALLET_PRIVATE_KEY"] = ""
os.environ["GOAT_WALLET_PUBKEY"] = ""

class ActionRequest(BaseModel):
    """Request model for agent actions"""
    connection: str
    action: str
    params: Optional[List[str]] = []

class ConfigureRequest(BaseModel):
    """Request model for configuring connections"""
    connection: str
    params: Optional[Dict[str, Any]] = {}

class TdxQuoteRequest(BaseModel):
    """Request model for TDX quotes"""
    report_data: str

class ExecuteCommandRequest(BaseModel):
    """Request model for command execution"""
    args: List[str]
class ServerState:
    """Simple state management for the server"""
    def __init__(self):
        self.cli = ZerePyCLI()
        self.agent_running = False
        self.agent_task = None
        self._stop_event = threading.Event()

    def _run_agent_loop(self):
        """Run agent loop in a separate thread"""
        try:
            log_once = False
            while not self._stop_event.is_set():
                if self.cli.agent:
                    try:
                        if not log_once:
                            logger.info("Loop logic not implemented")
                            log_once = True
                    except Exception as e:
                        logger.error(f"Error in agent action: {e}")
                        if self._stop_event.wait(timeout=30):
                            break
        except Exception as e:
            logger.error(f"Error in agent loop thread: {e}")
        finally:
            self.agent_running = False
            logger.info("Agent loop stopped")

    async def start_agent_loop(self):
        """Start the agent loop in background thread"""
        if not self.cli.agent:
            raise ValueError("No agent loaded")
        
        if self.agent_running:
            raise ValueError("Agent already running")

        self.agent_running = True
        self._stop_event.clear()
        self.agent_task = threading.Thread(target=self._run_agent_loop)
        self.agent_task.start()

    async def stop_agent_loop(self):
        """Stop the agent loop"""
        if self.agent_running:
            self._stop_event.set()
            if self.agent_task:
                self.agent_task.join(timeout=5)
            self.agent_running = False

def pubkey_exists() -> bool:
    """Check if a public key exists in environment variables"""
    return len(os.getenv("GOAT_WALLET_PUBKEY", "")) > 0

def get_pubkey_from_private_key(private_key_string: str) -> str:
    """Generate public key from private key"""
    if private_key_string.startswith("0x"):
        private_key_string = private_key_string[2:]
    private_key_bytes = bytes.fromhex(private_key_string)
    account = Web3().eth.account.from_key(private_key_bytes)
    return account.address

def set_private_key(private_key: str) -> None:
    """Set private key and derive public key"""
    if pubkey_exists():
        return
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    os.environ["GOAT_WALLET_PRIVATE_KEY"] = private_key
    pubkey = get_pubkey_from_private_key(private_key)
    os.environ["GOAT_WALLET_PUBKEY"] = pubkey
    logger.info(f"Private key set. Public key: {pubkey}")

class ZerePyServer:
    def __init__(self):
        self.app = FastAPI(title="ZerePy Server")
        self.state = ServerState()
        self.setup_middleware()
        self.setup_routes()

    def setup_middleware(self):
        """Setup CORS middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def _generate_solana_keypair(self):
        """Internal method to generate Solana keypair and set environment variables"""
        if not self.state.cli.agent:
            raise HTTPException(
                status_code=400, 
                detail="No agent loaded. Use /agents/{name}/load first."
            )
        
        try:
            client = AsyncTappdClient(DSTACK_SIMULATOR_ENDPOINT)
            random_path = f"/{str(uuid.uuid4())}"
            subject = "zerepy_v0.1.0"
            
            deriveKey = await client.derive_key(random_path, subject)
            seed = deriveKey.toBytes()[:32]
            
            # Generate Solana keypair
            keypair = Keypair.from_seed(seed)
            private_key = base58.b58encode(bytes(keypair)).decode("utf-8")
            public_key = str(keypair.pubkey())
            
            os.environ["SOLANA_PRIVATE_KEY"] = private_key
            os.environ["GOAT_WALLET_PRIVATE_KEY"] = private_key
            os.environ["GOAT_WALLET_PUBKEY"] = public_key
            
            logger.info(f"Keypair generated. Public key: {public_key}")
            
            return {
                "publicKey": public_key,
                "privateKey": private_key
            }
        
        except Exception as e:
            logger.error(f"Error generating keypair: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            """Server status endpoint"""
            return {
                "status": "running",
                "agent": self.state.cli.agent.name if self.state.cli.agent else None,
                "agent_running": self.state.agent_running
            }

        @self.app.get("/ping")
        async def ping():
            """Health check endpoint"""
            return {"status": "ok"}

        @self.app.get("/info")
        async def info():
            """Get agent configuration"""
            try:
                general = json.load(open("agents/general.json", "r"))
                default_agent_name = general["default_agent"]
                config = json.load(open(f"agents/{default_agent_name}.json", "r"))
                return {"config": config}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/derivekey/evm")
        async def derive_evm_key():
            """Get EVM keypair for the current agent"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded. Use /agents/{name}/load first")
            
            try:
                client = AsyncTappdClient(DSTACK_SIMULATOR_ENDPOINT)
                random_path = f"/{str(uuid.uuid4())}"
                subject = f"{self.state.cli.agent.name}_evm_v0.1.0"
                deriveKey = await client.derive_key(random_path, subject)

                assert isinstance(deriveKey, DeriveKeyResponse)
                key_bytes = deriveKey.toBytes()
                
                # Calculate keccak256 hash for EVM key
                web3 = Web3()
                private_key = web3.keccak(key_bytes).hex()
                account = web3.eth.account.from_key(private_key)
                
                return {
                    "address": account.address,
                    "privateKey": private_key
                }
            except Exception as e:
                logger.error(f"Error in derivekey/evm: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/derivekey/solana")
        async def derive_solana_key():
            """Get Solana keypair"""
            try:
                return await self._generate_solana_keypair()
            except Exception as e:
                logger.error(f"Error in derivekey/solana: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/derivekey/solana/validate")
        async def validate_solana_key():
            """Generate and validate a Solana keypair"""
            try:
                # Get keypair using shared logic
                keypair_response = await self._generate_solana_keypair()
                
                # Decode for validation
                private_key_bytes = base58.b58decode(keypair_response["privateKey"])
                
                # Validate through reconstruction
                reconstructed_keypair = Keypair.from_bytes(private_key_bytes)
                
                return {
                    **keypair_response,
                    "validation": {
                        "publicKeyMatches": str(reconstructed_keypair.pubkey()) == keypair_response["publicKey"],
                        "canReconstructFromPrivateKey": True,
                        "privateKeyLength": len(private_key_bytes),
                    }
                }
            
            except Exception as e:
                logger.error(f"Error validating Solana keypair: {e}")
                raise HTTPException(status_code=500, detail=str(e))


        @self.app.post("/tdxquote")
        async def tdxquote(request: TdxQuoteRequest):
            """Get TDX quote"""
            try:
                client = AsyncTappdClient(DSTACK_SIMULATOR_ENDPOINT)
                tdxQuote = await client.tdx_quote(request.report_data)
                assert isinstance(tdxQuote, TdxQuoteResponse)
                return {"tdxQuote": tdxQuote.quote}
            except Exception as e:
                logger.error(f"Error in tdxquote: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/execute_command")
        async def execute_command(request: ExecuteCommandRequest):
            """Execute a CLI command"""
            try:
                input_string = " ".join(request.args)
                try:
                    self.state.cli._handle_command(input_string)
                except Exception as e:
                    logger.error(f"Error executing command {input_string}: {e}")
                    raise HTTPException(status_code=500, detail=str(e))

                return {"status": "success"}
            except Exception as e:
                logger.error(f"Error in execute_command: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/agents")
        async def list_agents():
            """List available agents"""
            try:
                agents = []
                agents_dir = Path("agents")
                if agents_dir.exists():
                    for agent_file in agents_dir.glob("*.json"):
                        if agent_file.stem != "general":
                            agents.append(agent_file.stem)
                return {"agents": agents}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agents/{name}/load")
        async def load_agent(name: str):
            """Load a specific agent"""
            try:
                self.state.cli._load_agent_from_file(name)
                return {
                    "status": "success",
                    "agent": name
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/connections")
        async def list_connections():
            """List all available connections"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connections = {}
                for name, conn in self.state.cli.agent.connection_manager.connections.items():
                    connections[name] = {
                        "configured": conn.is_configured(),
                        "is_llm_provider": conn.is_llm_provider
                    }
                return {"connections": connections}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/action")
        async def agent_action(action_request: ActionRequest):
            """Execute a single agent action"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                result = await asyncio.to_thread(
                    self.state.cli.agent.perform_action,
                    connection=action_request.connection,
                    action=action_request.action,
                    params=action_request.params
                )
                return {"status": "success", "result": result}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/start")
        async def start_agent():
            """Start the agent loop"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                await self.state.start_agent_loop()
                return {"status": "success", "message": "Agent loop started"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/stop")
        async def stop_agent():
            """Stop the agent loop"""
            try:
                await self.state.stop_agent_loop()
                return {"status": "success", "message": "Agent loop stopped"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/connections/{name}/configure")
        async def configure_connection(name: str, config: ConfigureRequest):
            """Configure a specific connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                
                success = connection.configure(**config.params)
                if success:
                    return {"status": "success", "message": f"Connection {name} configured successfully"}
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to configure {name}")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/connections/{name}/status")
        async def connection_status(name: str):
            """Get configuration status of a connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
                
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                    
                return {
                    "name": name,
                    "configured": connection.is_configured(verbose=True),
                    "is_llm_provider": connection.is_llm_provider
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

def create_app():
    server = ZerePyServer()
    return server.app