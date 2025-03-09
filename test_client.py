from src.server.client import BerrySupplyChainClient

# Initialize client
client = BerrySupplyChainClient("http://localhost:8000")

# List available agents
agents = client.list_agents()
print(f"Available agents: {agents}")

# Load the BerryMonitorAgent
client.load_agent("BerryMonitorAgent")

# List connections
connections = client.list_connections()
print(f"Connections: {connections}")

# Try a direct action with parameters in the JSON payload
print("\nTrying direct API call with params...")
data = {
    "connection": "sonic",
    "action": "monitor-berry-temperature",
    "params": ["1", "4.5", "Warehouse-A"]
}
direct_result = client._make_request("POST", "/agent/action", json=data)
print(f"Direct API result: {direct_result}")

# Create a new batch
print("\nCreating batch...")
result = client.create_batch("Strawberry")
print(f"Batch created: {result}")

# Monitor temperature for a batch
print("\nMonitoring temperature...")
temp_result = client.monitor_temperature(batch_id=1, temperature=4.5, location="Warehouse-A")
print(f"Temperature monitored: {temp_result}")