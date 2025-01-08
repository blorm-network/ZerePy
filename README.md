# ZerePy

ZerePy is an open-source Python framework designed to let you deploy your own agents on X, powered by OpenAI/Anthropic/EternalAI LLMs.

ZerePy is built from a modularized version of the Zerebro backend. With ZerePy, you can launch your own agent with
similar core functionality as Zerebro. For creative outputs, you'll need to fine-tune your own model.

## Features

### Core Platform

- CLI interface for managing agents
- Modular connection system

### Social Platform Integrations

- Twitter/X
- Farcaster
- Echochambers

### Language Model Support

- OpenAI
- Anthropic
- EternalAI
- Ollama
- Hyperbolic

## Quickstart

The quickest way to start using ZerePy is to use our Replit template:

https://replit.com/@blormdev/ZerePy?v=1

1. Fork the template (you will need you own Replit account)
2. Click the run button on top
3. Voila! your CLI should be ready to use, you can jump to the configuration section

## Requirements

System:

- Python 3.10 or higher (3.10 and 3.11 are best for beginner users)
- Poetry 1.5 or higher

API keys:

- LLM: make an account and grab an API key (at least one)
  - OpenAI: https://platform.openai.com/api-keys
  - Anthropic: https://console.anthropic.com/account/keys
  - EternalAI: https://eternalai.oerg/api
  - Hyperbolic: https://app.hyperbolic.xyz
- Social (based on your needs):
  - X API: https://developer.x.com/en/docs/authentication/oauth-1-0a/api-key-and-secret
  - Farcaster: Warpcast recovery phrase
  - Echochambers: API key and endpoint

## Installation

1. First, install Poetry for dependency management if you haven't already:

Follow the steps here to use the official installation: https://python-poetry.org/docs/#installing-with-the-official-installer

2. Clone the repository:

```bash
git clone https://github.com/blorm-network/ZerePy.git
```

3. Go to the `zerepy` directory:

```bash
cd zerepy
```

4. Install dependencies:

```bash
poetry install --no-root
```

This will create a virtual environment and install all required dependencies.

## Usage

1. Activate the virtual environment:

```bash
poetry shell
```

2. Run the application:

```bash
poetry run python main.py
```

## Configure connections & launch an agent

1. Configure your desired connections:

   ```
   configure-connection twitter    # For Twitter/X integration
   configure-connection openai     # For OpenAI
   configure-connection anthropic  # For Anthropic
   configure-connection farcaster  # For Farcaster
   configure-connection eternalai  # For EternalAI
   ```

2. Use `list-connections` to see all available connections and their status

3. Load your agent (usually one is loaded by default, which can be set using the CLI or in agents/general.json):

   ```
   load-agent example
   ```

4. Start your agent:
   ```
   start
   ```

## Platform Features

### Twitter/X

- Post tweets from prompts
- Read timeline with configurable count
- Reply to tweets in timeline
- Like tweets in timeline

### Farcaster

- Post casts
- Reply to casts
- Like and requote casts
- Read timeline
- Get cast replies

### Echochambers

- Post new messages to rooms
- Reply to messages based on room context
- Read room history
- Get room information and topics

## Create your own agent

The secret to having a good output from the agent is to provide as much detail as possible in the configuration file. Craft a story and a context for the agent, and pick very good examples of tweets to include.

If you want to take it a step further, you can fine tune your own model: https://platform.openai.com/docs/guides/fine-tuning.

Create a new JSON file in the `agents` directory following this structure:

```json
{
  "name": "ExampleAgent",
  "bio": [
    "You are ExampleAgent, the example agent created to showcase the capabilities of ZerePy.",
    "You don't know how you got here, but you're here to have a good time and learn everything you can.",
    "You are naturally curious, and ask a lot of questions."
  ],
  "traits": ["Curious", "Creative", "Innovative", "Funny"],
  "examples": ["This is an example tweet.", "This is another example tweet."],
  "example_accounts": ["X_username_to_use_for_tweet_examples"],
  "default_provider": "hyperbolic", // optional, defaults to openai
  "loop_delay": 900,
  "config": [
    {
      "name": "twitter",
      "timeline_read_count": 10,
      "own_tweet_replies_count": 2,
      "tweet_interval": 5400
    },
    {
      "name": "farcaster",
      "timeline_read_count": 10,
      "cast_interval": 60
    },
    {
      "name": "openai",
      "model": "gpt-3.5-turbo"
    },
    {
      "name": "anthropic",
      "model": "claude-3-5-sonnet-20241022"
    },
    {
      "name": "eternalai",
      "model": "NousResearch/Hermes-3-Llama-3.1-70B-FP8",
      "chain_id": "45762"
    },
    {
      "name": "ollama",
      "base_url": "http://localhost:11434",
      "model": "llama3.2"
    },
    {
      "name": "hyperbolic",
      "model": "meta-llama/Meta-Llama-3-70B-Instruct"
    }
  ],
  "tasks": [
    { "name": "post-tweet", "weight": 1 },
    { "name": "reply-to-tweet", "weight": 1 },
    { "name": "like-tweet", "weight": 1 }
  ],
  "use_time_based_weights": false,
  "time_based_multipliers": {
    "tweet_night_multiplier": 0.4,
    "engagement_day_multiplier": 1.5
  }
}
```

## Available Commands

Use `help` in the CLI to see all available commands. Key commands include:

- `list-agents`: Show available agents
- `load-agent`: Load a specific agent
- `agent-loop`: Start autonomous behavior
- `agent-action`: Execute single action
- `list-connections`: Show available connections
- `list-actions`: Show available actions for a connection
- `configure-connection`: Set up a new connection
- `chat`: Start interactive chat with agent
- `get-provider-info`: Show current LLM provider and model
- `change-llm-provider`: Change the active LLM provider

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=blorm-network/ZerePy&type=Date)](https://star-history.com/#blorm-network/ZerePy&Date)

---

Made with ♥ @Blorm.xyz
