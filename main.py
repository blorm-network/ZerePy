from src.cli import ZerePyCLI
from pathlib import Path
import json
import logging
from datetime import datetime

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Add this near the start of your main execution
logger.info("Application started")

def ensure_directories():
    """Ensure required directories exist"""
    logger.info("Checking required directories")
    directories = [
        Path("agents"),
        Path.home() / '.zerepy'
    ]
    for directory in directories:
        if not directory.exists():
            logger.info(f"Creating directory: {directory}")
        directory.mkdir(exist_ok=True)

def setup():
    # Ensure directories exist
    ensure_directories()
    
    # Create general.json if it doesn't exist
    general_config = Path("agents") / "general.json"
    if not general_config.exists():
        logger.info("Creating default general.json configuration")
        with open(general_config, 'w') as f:
            json.dump({"default_agent": "example"}, f, indent=4)

if __name__ == "__main__":
    setup()
    cli = ZerePyCLI()
    cli.main_loop()
