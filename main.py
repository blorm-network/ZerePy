from src.cli import ZerePyCLI
from pathlib import Path
import json

def ensure_directories():
    """Ensure required directories exist"""
    directories = [
        Path("agents"),
        Path.home() / '.zerepy'
    ]
    for directory in directories:
        directory.mkdir(exist_ok=True)

def setup():
    # Ensure directories exist
    ensure_directories()
    
    # Create general.json if it doesn't exist
    general_config = Path("agents") / "general.json"
    if not general_config.exists():
        with open(general_config, 'w') as f:
            json.dump({"default_agent": "example"}, f, indent=4)

if __name__ == "__main__":
    setup()
    cli = ZerePyCLI()
    cli.main_loop()
