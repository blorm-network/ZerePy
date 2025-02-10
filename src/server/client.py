import requests
from typing import Optional, List, Dict, Any

class ZerePyClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        return self._make_request("GET", "/")

    def list_agents(self) -> List[str]:
        """List available agents"""
        response = self._make_request("GET", "/agents")
        return response.get("agents", [])

    def load_agent(self, agent_name: str) -> Dict[str, Any]:
        """Load a specific agent"""
        return self._make_request("POST", f"/agents/{agent_name}/load")

    def list_connections(self) -> Dict[str, Any]:
        """List available connections"""
        return self._make_request("GET", "/connections")

    def perform_action(self, connection: str, action: str, params: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute an agent action"""
        data = {
            "connection": connection,
            "action": action,
            "params": params or []
        }
        return self._make_request("POST", "/agent/action", json=data)

    def start_agent(self) -> Dict[str, Any]:
        """Start the agent loop"""
        return self._make_request("POST", "/agent/start")

    def stop_agent(self) -> Dict[str, Any]:
        """Stop the agent loop"""
        return self._make_request("POST", "/agent/stop")