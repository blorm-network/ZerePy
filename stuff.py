import json
import logging
import os
from src.lib.base_config import BaseConfig
from dotenv import load_dotenv

load_dotenv()

log_level = "INFO"
if log_level != "INFO":
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(lineno)d"
else:
    log_format = "%(message)s"

logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    try:

        config = BaseConfig()
        conn = config.agents["ExampleAgent"].list_connections()
        print(conn)
    except Exception as e:
        print(f"Error loading config: {e}")
