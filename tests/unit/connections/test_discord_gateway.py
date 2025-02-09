"""Tests for Discord Gateway client."""
import pytest
import websockets
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.connections.discord.gateway import DiscordGateway, GatewayConfig, OpCode

@pytest.mark.asyncio
async def test_gateway_connect():
    """Test gateway connection and heartbeat interval parsing."""
    config = GatewayConfig(token="test_token")
    gateway = DiscordGateway(config)
    
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.return_value = json.dumps({
            "op": OpCode.HELLO,
            "d": {"heartbeat_interval": 1000}
        })
        mock_connect.return_value = mock_ws
        
        await gateway.connect()
        assert gateway.heartbeat_interval == 1.0
        assert gateway._heartbeat_task is not None

@pytest.mark.asyncio
async def test_gateway_identify():
    """Test gateway identify with rate limit handling."""
    config = GatewayConfig(token="test_token")
    gateway = DiscordGateway(config)
    
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            json.dumps({
                "op": OpCode.HELLO,
                "d": {"heartbeat_interval": 1000}
            }),
            json.dumps({
                "t": "READY",
                "s": 1,
                "op": OpCode.DISPATCH,
                "d": {"session_id": "test_session"}
            })
        ]
        mock_connect.return_value = mock_ws
        
        await gateway.connect()
        assert gateway.session_id == "test_session"
        assert gateway.sequence == 1

@pytest.mark.asyncio
async def test_gateway_reconnect():
    """Test gateway reconnection handling."""
    config = GatewayConfig(token="test_token")
    gateway = DiscordGateway(config)
    
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            json.dumps({
                "op": OpCode.HELLO,
                "d": {"heartbeat_interval": 1000}
            }),
            json.dumps({
                "t": "READY",
                "s": 1,
                "op": OpCode.DISPATCH,
                "d": {"session_id": "test_session"}
            }),
            websockets.ConnectionClosed(1000, "test")
        ]
        mock_connect.return_value = mock_ws
        
        await gateway.connect()
        await gateway._handle_reconnect()
        
        assert mock_connect.call_count == 2
        assert gateway.ws is not None

@pytest.mark.asyncio
async def test_gateway_invalid_session():
    """Test invalid session handling."""
    config = GatewayConfig(token="test_token")
    gateway = DiscordGateway(config)
    
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            json.dumps({
                "op": OpCode.HELLO,
                "d": {"heartbeat_interval": 1000}
            }),
            json.dumps({
                "op": OpCode.INVALID_SESSION,
                "d": False
            })
        ]
        mock_connect.return_value = mock_ws
        
        await gateway.connect()
        await gateway._handle_invalid_session(False)
        
        assert gateway.session_id is None
        assert gateway.sequence is None

@pytest.mark.asyncio
async def test_gateway_rate_limit():
    """Test rate limit handling."""
    config = GatewayConfig(token="test_token")
    gateway = DiscordGateway(config)
    gateway._rate_limit_remaining = 0
    gateway._rate_limit_reset = asyncio.get_event_loop().time() + 1
    
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.return_value = json.dumps({
            "op": OpCode.HELLO,
            "d": {"heartbeat_interval": 1000}
        })
        mock_connect.return_value = mock_ws
        
        start_time = asyncio.get_event_loop().time()
        await gateway._send_heartbeat()
        end_time = asyncio.get_event_loop().time()
        
        assert end_time - start_time >= 1.0
