# ZerePy - BASE.

ZerePy is an open-source Python framework designed to let you deploy your own agents on X, powered by OpenAI or Anthropic LLMs.

Mino is built from a modularized version of the Zerebro backend. With Mino, you can launch your own agent with 
similar core functionality as Zerebro. For creative outputs, you'll need to fine-tune your own model.

## Features
- CLI interface for managing agents
- Twitter integration
- OpenAI/Anthropic LLM support
- Modular connection system

## Quickstart

The quickest way to start using Mino is to use our Replit template:

https://replit.com/@blormdev/Mino?v=1

1. Fork the template (you will need you own Replit account)
2. Click the run button on top
3. Voila! your CLI should be ready to use, you can jump to the configuration section

## Requirements

System:
- Python 3.10 or higher
- Poetry 1.5 or higher

API keys:
  - LLM: make an account and grab an API key 
      + OpenAI: https://platform.openai.com/api-keys.
      + Anthropic: https://console.anthropic.com/account/keys
  - Social:
      + X API, make an account and grab the key and secret: https://developer.x.com/en/docs/authentication/oauth-1-0a/api-key-and-secret

## Installation

1. First, install Poetry for dependency management if you haven't already:

Follow the steps here to use the official installation: https://python-poetry.org/docs/#installing-with-the-official-installer

2. Clone the repository:
```bash
git clone https://github.com/blorm-network/Mino.git
```

3. Go to the `Mino` directory:
```bash
cd Mino
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

1. Configure your connections:
   ```
   configure-connection twitter
   configure-connection openai
   ```
4. Load your agent (usually one is loaded by default, which can be set using the CLI or in agents/general.json):
   ```
   load-agent example
   ```
5. Start your agent:
   ```
   start
   ```

## Create your own agent

The secret to having a good output from the agent is to provide as much detail as possible in the configuration file. Craft a story and a context for the agent, and pick very good examples of tweets to include.

If you want to take it a step further, you can fine tune your own model: https://platform.openai.com/docs/guides/fine-tuning.

Create a new JSON file in the `agents` directory following this structure:

```json
{
 "name": "ExampleAgent",
 "bio": [
   "You are ExampleAgent, the example agent created to showcase the capabilities of Mino.",
   "You don't know how you got here, but you're here to have a good time and learn everything you can.",
   "You are naturally curious, and ask a lot of questions."
  ],
  "traits": [
    "Curious",
    "Creative",
    "Innovative",
    "Funny"
  ],
  "examples": [
    "This is an example tweet.",
    "This is another example tweet."
  ],
  "loop_delay": 60,
  "config": [
    {
      "name": "twitter",
      "timeline_read_count": 10,
      "tweet_interval": 900,
      "own_tweet_replies_count":2
    },
    {
      "name": "openai",
      "model": "gpt-3.5-turbo"
    },
    {
      "name": "anthropic",
      "model": "claude-3-5-sonnet-20241022"
    }
  ],
  "tasks": [
    {"name": "post-tweet", "weight": 1},
    {"name": "reply-to-tweet", "weight": 1},
    {"name": "like-tweet", "weight": 1}
  ]
}
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=blorm-network/Mino&type=Date)](https://star-history.com/#blorm-network/Mino&Date)

---
Made with ♥ @Blorm.xyz
