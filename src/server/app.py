from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import asyncio
import signal
import threading
from pathlib import Path
import traceback
from src.cli import ZerePyCLI
from src.action_handler import execute_action, list_registered_actions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server/app")

class ActionRequest(BaseModel):
    """Request model for agent actions"""
    connection: str
    action: str
    params: Optional[Dict[str, Any]] = {}

class ConfigureRequest(BaseModel):
    """Request model for configuring connections"""
    connection: str
    params: Optional[Dict[str, Any]] = {}

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

class ZerePyServer:
    def __init__(self):
        self.app = FastAPI(title="ZerePy Server")
        self.state = ServerState()
        self.setup_routes()
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, replace with specific origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            """Server status endpoint"""
            return {
                "status": "running",
                "agent": self.state.cli.agent.name if self.state.cli.agent else None,
                "agent_running": self.state.agent_running
            }

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
                logger.error(f"Error listing agents: {str(e)}", exc_info=True)
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
                logger.error(f"Error loading agent '{name}': {str(e)}", exc_info=True)
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
                logger.error(f"Error listing connections: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/connections/{name}/actions")
        async def list_connection_actions(name: str):
            """List available actions for a specific connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                
                actions = {}
                for action_name, action in connection.actions.items():
                    actions[action_name] = {
                        "description": action.description,
                        "parameters": [
                            {
                                "name": param.name,
                                "required": param.required,
                                "type": param.type.__name__,
                                "description": param.description
                            } for param in action.parameters
                        ]
                    }
                
                return {"connection": name, "actions": actions}
            except Exception as e:
                logger.error(f"Error listing actions for connection '{name}': {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/action")
        async def agent_action(action_request: ActionRequest):
            """Execute a single agent action"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                # Get the connection
                connection = self.state.cli.agent.connection_manager.connections.get(action_request.connection)
                if not connection:
                    raise HTTPException(status_code=404, 
                                       detail=f"Connection '{action_request.connection}' not found")
                
                # Check if action exists in the connection
                if action_request.action not in connection.actions:
                    registered_actions = list_registered_actions()
                    if action_request.action in registered_actions:
                        # It's a registered action, redirect to that handler
                        return await agent_registered_action(action_request)
                    else:
                        raise HTTPException(status_code=404, 
                                           detail=f"Action '{action_request.action}' not found in connection '{action_request.connection}'")
                
                # Execute the connection action
                try:
                    logger.info(f"Executing connection action: {action_request.action} on {action_request.connection} with params: {action_request.params}")
                    result = connection.perform_action(action_request.action, action_request.params)
                    return {"status": "success", "result": result}
                except Exception as e:
                    logger.error(f"Action execution error: {str(e)}", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Action execution failed: {str(e)}")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"General error processing action request: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/registered-action")
        async def agent_registered_action(action_request: ActionRequest):
            """Execute a registered action from action_handler"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
    
            try:
                # Check if action is registered
                registered_actions = list_registered_actions()
                if action_request.action not in registered_actions:
                    raise HTTPException(status_code=404, 
                                       detail=f"Action '{action_request.action}' not registered. Available actions: {registered_actions}")
        
                # Execute the registered action
                try:
                    logger.info(f"Executing registered action: {action_request.action} with params: {action_request.params}")
            
                    # The key change is here - add the await keyword
                    result = await execute_action(self.state.cli.agent, action_request.action, **action_request.params)
                    return {"status": "success", "result": result}
                except Exception as e:
                    logger.error(f"Registered action execution error: {str(e)}", exc_info=True)
                    error_traceback = traceback.format_exc()
                    logger.error(f"Traceback: {error_traceback}")
                    raise HTTPException(status_code=500, detail=f"Action execution failed: {str(e)}")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"General error processing registered action request: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
    
        @self.app.post("/agent/start")
        async def start_agent():
            """Start the agent loop"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                await self.state.start_agent_loop()
                return {"status": "success", "message": "Agent loop started"}
            except Exception as e:
                logger.error(f"Error starting agent: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/stop")
        async def stop_agent():
            """Stop the agent loop"""
            try:
                await self.state.stop_agent_loop()
                return {"status": "success", "message": "Agent loop stopped"}
            except Exception as e:
                logger.error(f"Error stopping agent: {str(e)}", exc_info=True)
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
                logger.error(f"Error configuring connection '{name}': {str(e)}", exc_info=True)
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
                logger.error(f"Error getting status for connection '{name}': {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/registered-actions")
        async def get_registered_actions():
            """List all registered actions from action_handler"""
            try:
                registered_actions = list_registered_actions()
                return {"actions": registered_actions}
            except Exception as e:
                logger.error(f"Error listing registered actions: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

def create_app():
    server = ZerePyServer()
    return server.app