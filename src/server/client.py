import requests
from typing import Dict, Any, List, Optional, Union

class BerrySupplyChainClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with enhanced error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # Ensure proper content type header is set
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            if method in ["POST", "PUT", "PATCH"] and 'json' in kwargs:
                kwargs['headers']['Content-Type'] = 'application/json'
                
            response = requests.request(method, url, **kwargs)
            print(f"DEBUG: {method} {url} - Status: {response.status_code}")
            
            # Try to parse response as JSON, but handle non-JSON responses
            try:
                result = response.json() if response.content else {}
            except ValueError:
                print(f"NOTICE: Response is not JSON: {response.text[:100]}...")
                result = {"raw_response": response.text}
                
            # Check for successful status code
            response.raise_for_status()
            return result
        except requests.exceptions.RequestException as e:
            print(f"ERROR: {method} {url} - {str(e)}")
            # Try to include response details in the error if available
            error_details = {}
            try:
                if hasattr(e, 'response') and e.response:
                    error_details = e.response.json()
            except:
                if hasattr(e, 'response') and e.response:
                    error_details = {"text": e.response.text}
            
            print(f"ERROR DETAILS: {error_details}")
            raise Exception(f"Request failed: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        return self._make_request("GET", "/")

    def list_agents(self) -> List[str]:
        """List available agents"""
        response = self._make_request("GET", "/agents")
        return response.get("agents", [])

    def load_agent(self, agent_name: str) -> Dict[str, Any]:
        """Load a specific agent using POST method"""
        return self._make_request("POST", f"/agents/{agent_name}/load")

    def list_connections(self) -> Dict[str, Any]:
        """List available connections"""
        return self._make_request("GET", "/connections")
    
    def list_connection_actions(self, connection: str) -> Dict[str, Any]:
        """List available actions for a specific connection"""
        return self._make_request("GET", f"/connections/{connection}/actions")

    def perform_action(self, action: str, connection: str = "sonic", params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an agent action
        
        Args:
            action: Action name (without embedded parameters)
            connection: Connection name to use (default: "sonic")
            params: Dictionary of named parameters for the action
        """
        # Create the request data
        data = {
            "connection": connection,
            "action": action,
            "params": params or {}
        }
        
        return self._make_request("POST", "/agent/action", json=data)
        
    def perform_registered_action(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a registered action (from action_handler)
        
        Args:
            action: Action name (without embedded parameters)
            params: Dictionary of named parameters for the action
        """
        # Create the request data
        data = {
            "connection": "registered",
            "action": action,
            "params": params or {}
        }
        
        return self._make_request("POST", "/agent/registered-action", json=data)

    # Berry-specific helper methods
    def monitor_temperature(self, batch_id: int, temperature: float, location: str) -> Dict[str, Any]:
        """Monitor temperature for a specific batch"""
        params = {
            "batch_id": batch_id,
            "temperature": temperature,
            "location": location
        }
        return self.perform_registered_action(action="monitor-berry-temperature", params=params)
    
    def create_batch(self, berry_type: str = "Strawberry") -> Dict[str, Any]:
        """Create a new batch"""
        params = {
            "action": "create",
            "berry_type": berry_type
        }
        return self.perform_registered_action(action="manage-batch-lifecycle", params=params)
    
    def complete_shipment(self, batch_id: int) -> Dict[str, Any]:
        """Complete a shipment"""
        action = f"manage-batch-lifecycle:complete:{batch_id}"
        return self.perform_action(action=action)
    
    def get_batch_status(self, batch_id: int) -> Dict[str, Any]:
        """Get batch status"""
        action = f"manage-batch-lifecycle:status:{batch_id}"
        return self.perform_action(action=action)
    
    def assess_quality(self, batch_id: int) -> Dict[str, Any]:
        """Assess quality for a specific batch"""
        action = f"manage-berry-quality:{batch_id}"
        return self.perform_action(action=action)
    
    def process_recommendations(self, batch_id: int) -> Dict[str, Any]:
        """Process agent recommendations for a batch"""
        action = f"process-agent-recommendations:{batch_id}"
        return self.perform_action(action=action)
    
    def run_batch_sequence(self, berry_type: str, temperatures: List[float], 
                           locations: List[str], complete_shipment: bool = False) -> Dict[str, Any]:
        """
        Run a complete batch sequence
        Format all parameters into a single string with separators
        """
        # Join temperatures and locations with commas
        temps_str = ",".join(str(t) for t in temperatures)
        locations_str = ",".join(locations)
        complete_str = "true" if complete_shipment else "false"
        
        action = f"manage-batch-sequence:{berry_type}:{temps_str}:{locations_str}:{complete_str}"
        return self.perform_action(action=action)
    
    # Additional helper methods for frontend integration
    def get_batch_history(self, batch_id: int) -> Dict[str, Any]:
        """
        Get full batch history including temperature readings and predictions
        """
        action = f"manage-batch-lifecycle:report:{batch_id}"
        return self.perform_action(action=action)
    
    def get_health_metrics(self, reset_counters: bool = False) -> Dict[str, Any]:
        """
        Get system health metrics
        """
        action = f"system-health-check:{reset_counters}"
        return self.perform_action(action=action)