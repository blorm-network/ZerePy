"""Discord Gateway WebSocket client for real-time events."""
from typing import Dict, Any, Optional, Callable, List
import asyncio
import json
import logging
import random
import websockets
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime, timedelta

logger = logging.getLogger("discord.gateway")

class OpCode(IntEnum):
    """Discord Gateway operation codes."""
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE_UPDATE = 3
    VOICE_STATE_UPDATE = 4
    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

@dataclass
class GatewayConfig:
    token: str
    intents: int = 513  # Default intents
    version: int = 10
    encoding: str = "json"

class DiscordGateway:
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.ws = None
        self.session_id = None
        self.sequence = None
        self.heartbeat_interval = None
        self._heartbeat_task = None
        self._handlers: Dict[str, Callable] = {}
        self._rate_limit_remaining = 120
        self._rate_limit_reset = 0
        
    async def connect(self) -> None:
        """Establish WebSocket connection with Discord Gateway."""
        url = f"wss://gateway.discord.gg/?v={self.config.version}&encoding={self.config.encoding}"
        self.ws = await websockets.connect(url)
        await self._handle_hello()
        await self._identify()
        
    async def _handle_hello(self) -> None:
        """Handle the HELLO event from Discord Gateway."""
        try:
            data = await self.ws.recv()
            payload = json.loads(data)
            
            if payload.get('op') != OpCode.HELLO:
                raise ValueError(f"Expected HELLO op code, got {payload.get('op')}")
                
            self.heartbeat_interval = payload['d']['heartbeat_interval'] / 1000
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Received HELLO event, started heartbeat")
            
        except Exception as e:
            logger.error(f"Failed to handle HELLO event: {e}")
            raise
        
    async def _identify(self):
        """Send IDENTIFY event to Discord Gateway."""
        try:
            if self._rate_limit_remaining <= 0:
                wait_time = self._rate_limit_reset - asyncio.get_event_loop().time()
                if wait_time > 0:
                    logger.warning(f"Rate limited, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            
            payload = {
                "op": OpCode.IDENTIFY,
                "d": {
                    "token": self.config.token,
                    "intents": self.config.intents,
                    "properties": {
                        "os": "linux",
                        "browser": "zerepy",
                        "device": "zerepy"
                    }
                }
            }
            
            await self.ws.send(json.dumps(payload))
            self._rate_limit_remaining -= 1
            logger.info("Sent IDENTIFY event")
            
            # Wait for READY event
            data = await self.ws.recv()
            payload = json.loads(data)
            
            if payload.get('t') == 'READY':
                self.session_id = payload['d']['session_id']
                logger.info(f"Received READY event with session ID: {self.session_id}")
            else:
                logger.warning(f"Expected READY event, got {payload.get('t')}")
            
        except Exception as e:
            logger.error(f"Failed to send IDENTIFY event: {e}")
            raise
            
    async def handle_event(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register event handler for specific event type."""
        self._handlers[event_type] = callback
        
    async def _handle_dispatch(self, payload: Dict[str, Any]) -> None:
        """Handle dispatched events from Discord Gateway."""
        try:
            event_type = payload.get('t')
            if not event_type:
                return
                
            self.sequence = payload.get('s')
            
            if event_type in self._handlers:
                await self._handlers[event_type](payload['d'])
                logger.debug(f"Handled event: {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to handle dispatch event: {e}")
            
    async def _process_messages(self) -> None:
        """Process incoming Gateway messages."""
        try:
            while True:
                data = await self.ws.recv()
                payload = json.loads(data)
                
                op = payload.get('op')
                if op == OpCode.DISPATCH:
                    await self._handle_dispatch(payload)
                elif op == OpCode.HEARTBEAT:
                    await self._send_heartbeat()
                elif op == OpCode.RECONNECT:
                    await self._handle_reconnect()
                elif op == OpCode.INVALID_SESSION:
                    await self._handle_invalid_session(payload.get('d', False))
                elif op == OpCode.HELLO:
                    # Already handled in connect()
                    pass
                elif op == OpCode.HEARTBEAT_ACK:
                    logger.debug("Received heartbeat ACK")
                else:
                    logger.warning(f"Unknown operation code: {op}")
                    
        except websockets.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"Error processing messages: {e}")
            raise
            
    async def _heartbeat_loop(self) -> None:
        """Send heartbeats at the specified interval."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
            raise
            
    async def _send_heartbeat(self) -> None:
        """Send heartbeat with sequence number."""
        try:
            if self._rate_limit_remaining <= 0:
                wait_time = self._rate_limit_reset - asyncio.get_event_loop().time()
                if wait_time > 0:
                    logger.warning(f"Rate limited, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    
            payload = {
                "op": OpCode.HEARTBEAT,
                "d": self.sequence
            }
            await self.ws.send(json.dumps(payload))
            self._rate_limit_remaining -= 1
            logger.debug("Sent heartbeat")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            raise
            
    async def _handle_reconnect(self) -> None:
        """Handle reconnection when requested by Discord."""
        try:
            if self.ws:
                await self.ws.close()
                
            self.ws = await websockets.connect(
                f"wss://gateway.discord.gg/?v={self.config.version}&encoding={self.config.encoding}"
            )
            
            if self.session_id and self.sequence:
                await self._resume()
            else:
                await self._handle_hello()
                await self._identify()
                
        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            raise
            
    async def _resume(self) -> None:
        """Resume a disconnected session."""
        try:
            payload = {
                "op": OpCode.RESUME,
                "d": {
                    "token": self.config.token,
                    "session_id": self.session_id,
                    "seq": self.sequence
                }
            }
            await self.ws.send(json.dumps(payload))
            logger.info("Sent RESUME")
            
        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            raise
            
    async def _handle_invalid_session(self, resumable: bool) -> None:
        """Handle invalid session response."""
        try:
            logger.warning(f"Session invalidated, resumable: {resumable}")
            
            if self.ws:
                await self.ws.close()
                
            await asyncio.sleep(1 + (2 * random.random()))  # Random delay between 1-3s
            
            self.ws = await websockets.connect(
                f"wss://gateway.discord.gg/?v={self.config.version}&encoding={self.config.encoding}"
            )
            
            if resumable and self.session_id and self.sequence:
                await self._resume()
            else:
                self.session_id = None
                self.sequence = None
                await self._handle_hello()
                await self._identify()
                
        except Exception as e:
            logger.error(f"Failed to handle invalid session: {e}")
            raise
