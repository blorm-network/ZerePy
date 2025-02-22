# ZerePy Server Mode Quick Start

## Initial Setup

NOTE: valid ANTHROPIC_API_KEY required in .env

1. Start the server:
```bash
poetry run python main.py --server
```

2. Check server status:
```bash
curl http://localhost:8000/
```
Response:
```json
{
    "status": "running",
    "agent": null,
    "agent_running": false
}
```

3. Load your agent:
```bash
curl -X POST http://localhost:8000/agents/example/load
```
Response:
```json
{
    "status": "success",
    "agent": "example"
}
```

4. Check connection status:
```bash
curl http://localhost:8000/connections
```

## Making Process Commands

### Request Format

```
POST /agent/action

Headers:
Content-Type: application/json

Request Body:
{
    "connection": string,  // Name of the connection (e.g. "brain")
    "action": string,     // Action to perform (e.g. "process-command") 
    "params": string[]    // Array of parameters for the action
}
```

### Example Request

```bash
curl -X POST http://localhost:8000/agent/action \
  -H "Content-Type: application/json" \
  -d '{
    "connection": "brain",
    "action": "process-command", 
    "params": ["help me swap .01 eth for usdc on base"]
  }'
```

### Example Response

Success:
```json
{
    "status": "success",
    "result": "I'll help you swap 0.01 ETH for USDC on Base network..."
}
```

Error:
```json
{
    "status": "error",
    "result": "Error message details..."
}
```

## Troubleshooting

If connections aren't configured automatically from your agent.json:

1. Configure Brain connection:
```bash
curl -X POST http://localhost:8000/connections/brain/configure \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
        "llm_provider": "anthropic",
        "model": "claude-3-sonnet-20240229"
    }
  }'
```

2. Check specific connection status:
```bash
curl http://localhost:8000/connections/brain/status
```
Response:
```json
{
    "name": "brain",
    "configured": true,
    "is_llm_provider": false
}
```